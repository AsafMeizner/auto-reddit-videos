import random
import json
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip, vfx
import asyncio
import subprocess

# Load your JSON file with stories
with open('reddit_posts.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

# Select a random story
selected_post = random.choice(posts)
story_title = selected_post['title']
story_text = selected_post['text']
# Add title to story text for better TTS
story_text = story_title + ' ' + story_text

# Fix abbreviations
abbreviations = {
    'aita': 'Am I the bastard',
    'wibta': 'Would I be the bastard',
    'yta': 'You are the bastard',
    'nta': 'Not the bastard',
    'ynta': 'You are not the bastard',
    'tl;dr': 'Too long; didn’t read',
    'btw': 'By the way',
    'ftw': 'For the win',
    'imo': 'In my opinion',
    'imho': 'In my humble opinion',
    'fwiw': 'For what it’s worth',
    'iirc': 'If I recall correctly'
}

for abbrev, full in abbreviations.items():
    story_text = story_text.lower().replace(abbrev, full)

print(f"Selected Post: {story_title}")

# Load Whisper model (using base model, can be changed to medium/large)
model = whisper.load_model("base")

# Function to generate SRT from transcription
def generate_srt(transcription, filename):
    srt_content = []
    counter = 1

    # Iterate through transcription segments
    for segment in transcription:
        for word_info in segment['words']:  # Loop through each word
            word = word_info['word']
            start_time = word_info['start']
            end_time = word_info['end']
            
            # Format start and end times to SRT format
            start_srt_time = format_srt_time(start_time)
            end_srt_time = format_srt_time(end_time)
            
            # SRT format: number, start --> end, text
            srt_content.append(f"{counter}\n{start_srt_time} --> {end_srt_time}\n{word.strip()}\n")
            counter += 1

    # Write to SRT file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_content))

# Function to format time into SRT format
def format_srt_time(seconds):
    ms = int((seconds % 1) * 1000)
    seconds = int(seconds)
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

# Function to transcribe audio to SRT
def transcribe_audio_to_srt(audio_file, srt_file):
    # Transcribe the audio file using Whisper, enabling word-level timestamps
    result = model.transcribe(audio_file, word_timestamps=True)

    # Get the segments from the transcription
    transcription_segments = result['segments']

    # Generate the SRT file
    generate_srt(transcription_segments, srt_file)

# Function to split the text into parts of at least 1 minute
def split_text_into_segments(story_text, min_word_count_per_part=150):
    words = story_text.split()
    segments = []
    current_segment = []

    for word in words:
        current_segment.append(word)
        if len(current_segment) >= min_word_count_per_part:
            segments.append(' '.join(current_segment))
            current_segment = []

    # Append remaining words to the last segment
    if current_segment:
        segments.append(' '.join(current_segment))

    return segments

# Function to generate speech for each part with title and part number
async def generate_speech_with_title(text, part_number, audio_filename='story_audio.mp3'):
    from edge_tts import Communicate

    # List of available English voices
    english_voices = [
        "en-AU-NatashaNeural", "en-AU-WilliamNeural", "en-CA-ClaraNeural", "en-CA-LiamNeural",
        "en-HK-SamNeural", "en-HK-YanNeural", "en-IN-NeerjaNeural", "en-IN-PrabhatNeural",
        "en-IE-ConnorNeural", "en-IE-EmilyNeural", "en-KE-AsiliaNeural", "en-KE-ChilembaNeural",
        "en-NZ-MitchellNeural", "en-NZ-MollyNeural", "en-NG-AbeoNeural", "en-NG-EzinneNeural",
        "en-PH-JamesNeural", "en-PH-RosaNeural", "en-SG-LunaNeural", "en-SG-WayneNeural",
        "en-ZA-LeahNeural", "en-ZA-LukeNeural", "en-TZ-ElimuNeural", "en-TZ-ImaniNeural",
        "en-GB-LibbyNeural", "en-GB-MaisieNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural",
        "en-GB-ThomasNeural", "en-US-AriaNeural", "en-US-AnaNeural", "en-US-ChristopherNeural",
        "en-US-EricNeural", "en-US-GuyNeural", "en-US-JennyNeural", "en-US-MichelleNeural",
        "en-US-RogerNeural", "en-US-SteffanNeural"
    ]

    # Select a random voice
    random_voice = random.choice(english_voices)

    # Prepend the title and part number to the text
    text_with_part = f"{story_title}, Part {part_number}. {text}"

    # Instantiate the Communicate class
    gen = Communicate(text_with_part, voice=random_voice)

    # Generate the speech in chunks and save to file
    async for chunk in gen.stream():
        if chunk["type"] == "audio":
            with open(audio_filename, "ab") as audio_file:
                audio_file.write(chunk["data"])

# Function to create video without subtitles for each part
def create_video_for_audio_part(gameplay_file, audio_file, part_number):
    try:
        # Load the generated audio file and get its duration
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration

        # Load gameplay footage and get its duration
        gameplay_clip = VideoFileClip(gameplay_file)
        gameplay_duration = gameplay_clip.duration

        # Choose a random start time within the gameplay, ensuring there's enough time for the audio
        max_start_time = gameplay_duration - audio_duration
        if max_start_time <= 0:
            start_time = 0  # If the gameplay is shorter than the audio, use the beginning
        else:
            start_time = random.uniform(0, max_start_time)

        # Extract the portion of the gameplay that matches the audio duration
        gameplay_segment = gameplay_clip.subclip(start_time, start_time + audio_duration)

        # Resize the gameplay to 9:16 aspect ratio (portrait) and center the crop
        gameplay_segment = gameplay_segment.resize(height=1080)  # Set height to 1080px
        gameplay_segment = gameplay_segment.fx(vfx.crop, x_center=gameplay_segment.w / 2, width=608)  # Crop to center for 9:16 aspect ratio

        # Set the audio
        final_video = gameplay_segment.set_audio(audio_clip)

        # Export the final video
        video_filename = f"no_subtitles_output_video_part_{part_number}.mp4"
        final_video.write_videofile(video_filename, codec="libx264", fps=24, threads=16)

        return video_filename
    finally:
        # Ensure clips are closed properly
        try:
            audio_clip.close()
            gameplay_clip.close()
            final_video.close()
        except Exception as e:
            print(f"Error closing resources: {e}")

# Function to burn subtitles for each part
def add_subtitles_to_video(video_file, subtitle_file, part_number, font_path):
    output_file = f"subtitled_output_video_part_{part_number}.mp4"
    ffmpeg_command = [
        'ffmpeg',
        '-i', video_file,
        '-vf', f"subtitles={subtitle_file}:force_style='FontName={font_path},FontSize=32,PrimaryColour=&H000000FF&,Outline=2,OutlineColour=&H00000000&,Alignment=10,MarginV=0'",
        '-c:a', 'copy',
        output_file
    ]
    subprocess.run(ffmpeg_command)
    return output_file

# Full workflow
async def full_workflow():
    # Step 1: Split the story text into segments
    segment_texts = split_text_into_segments(story_text)
    num_segments = len(segment_texts)

    # Step 2: Generate audio and create videos without subtitles for each part
    for i, segment_text in enumerate(segment_texts):
        part_number = i + 1
        audio_filename = f'story_audio_part_{part_number}.mp3'

        # Generate speech with title and part number
        await generate_speech_with_title(segment_text, part_number, audio_filename)

        # Create the video without subtitles for the part
        create_video_for_audio_part("gameplay.mp4", audio_filename, part_number)

    # Step 3: Generate subtitles and burn into videos for each part
    for i in range(num_segments):
        part_number = i + 1
        audio_filename = f'story_audio_part_{part_number}.mp3'
        srt_filename = f'story_subtitles_part_{part_number}.srt'
        video_without_subtitles = f"no_subtitles_output_video_part_{part_number}.mp4"

        # Generate unique subtitles for each part
        transcribe_audio_to_srt(audio_filename, srt_filename)

        # Burn subtitles into the video for the part
        add_subtitles_to_video(video_without_subtitles, srt_filename, part_number, "Bangers")

# Run the full workflow
asyncio.run(full_workflow())
