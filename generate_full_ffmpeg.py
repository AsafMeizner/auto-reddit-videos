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
        # Load the MP3 audio file and get its duration using MoviePy
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration

        # Load the gameplay video using MoviePy
        gameplay_clip = VideoFileClip(gameplay_file)
        gameplay_duration = gameplay_clip.duration

        # Choose a random start time ensuring there's enough time for the audio
        max_start_time = gameplay_duration - audio_duration
        if max_start_time <= 0:
            start_time = 0
        else:
            start_time = random.uniform(0, max_start_time)

        # Step 1: Extract the video segment without audio
        video_segment_output = f"gameplay_segment_part_{part_number}.mp4"
        ffmpeg_command_1 = [
            'ffmpeg',
            '-y',  # Overwrite the output file
            '-ss', str(start_time),  # Start time for gameplay
            '-i', gameplay_file,  # Input gameplay file
            '-t', str(audio_duration),  # Clip duration based on audio length
            '-vf', 'scale=-1:1080,crop=608:1080',  # Resize to 1080px height, crop to 9:16 aspect ratio
            '-r', '24',  # Set frame rate to 24 fps
            '-an',  # Remove the original audio from the video
            '-c:v', 'libx264',  # Video codec
            video_segment_output  # Output video file
        ]
        subprocess.run(ffmpeg_command_1, check=True)

        # Step 2: Merge the extracted video (without audio) with the MP3 audio
        final_video_output = f"no_subtitles_output_video_part_{part_number}.mp4"
        ffmpeg_command_2 = [
            'ffmpeg',
            '-y',  # Overwrite the output file
            '-i', video_segment_output,  # Input video without audio
            '-i', audio_file,  # Input MP3 audio file
            '-map', '0:v:0',  # Map the video from the first input
            '-map', '1:a:0',  # Map the audio from the second input (MP3)
            '-c:v', 'copy',  # Copy the video stream without re-encoding
            '-c:a', 'copy',  # Copy the audio stream without re-encoding
            '-shortest',  # Trim the output to the shortest stream
            final_video_output  # Output file
        ]
        subprocess.run(ffmpeg_command_2, check=True)

        return final_video_output

    finally:
        # Ensure proper cleanup of the loaded clips
        try:
            audio_clip.close()
            gameplay_clip.close()
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
