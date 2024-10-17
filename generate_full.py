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
# add title to story text for better TTS
story_text = story_title + ' ' + story_text

# fix abbreviations
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

# Function to generate speech and create the audio file (ensure it's created first)
async def generate_speech_with_edge_tts(text, audio_filename='story_audio.mp3'):
    from edge_tts import Communicate

    # make it choose a random voice from all the available English voices
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

    # Select a random voice from the list
    random_voice = random.choice(english_voices)

    # Instantiate the Communicate class with the selected voice
    gen = Communicate(text, voice=random_voice)

    # Use the 'speak' method and collect the results
    async for chunk in gen.stream():
        if chunk["type"] == "audio":
            # Save the audio chunk to a file
            with open(audio_filename, "ab") as audio_file:  # 'ab' to append in case of multiple chunks
                audio_file.write(chunk["data"])

# Function to create video without subtitles
def create_video_without_subtitles(gameplay_file, audio_file):
    try:
        # Load the generated audio file and get its duration
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration  # Should be around 4 minutes in your case

        # Load gameplay footage and get its duration
        gameplay_clip = VideoFileClip(gameplay_file)
        gameplay_duration = gameplay_clip.duration

        # Choose a random start time within the gameplay, ensuring there's enough time for the audio
        max_start_time = gameplay_duration - audio_duration
        if max_start_time <= 0:
            start_time = 0  # In case the gameplay is shorter than the audio, use the beginning
        else:
            start_time = random.uniform(0, max_start_time)

        # Extract the portion of the gameplay that matches the audio duration (crop it)
        gameplay_segment = gameplay_clip.subclip(start_time, start_time + audio_duration)

        # Resize the gameplay to 9:16 aspect ratio (portrait)
        gameplay_segment = gameplay_segment.resize(height=1080)  # Set the height to 1080px
        gameplay_segment = gameplay_segment.fx(vfx.crop, x_center=gameplay_segment.w / 2, width=608)  # Crop width for 9:16

        # Set the audio
        final_video = gameplay_segment.set_audio(audio_clip)

        # Export the final video without subtitles
        final_video.write_videofile("no_subtitles_output_video.mp4", codec="libx264", fps=24, remove_temp=True, write_logfile=False, threads=16)
    finally:
        # Ensure clips are closed properly
        try:
            audio_clip.close()
            gameplay_clip.close()
            final_video.close()
        except Exception as e:
            print(f"Error closing resources: {e}")

# Function to burn subtitles using ffmpeg
def add_styled_subtitles_with_ffmpeg(video_file, subtitle_file, output_file, font_path):
    # Use ffmpeg to burn subtitles with custom styles
    ffmpeg_command = [
        'ffmpeg',
        '-i', video_file,  
        '-vf', f"subtitles={subtitle_file}:force_style='FontName={font_path},FontSize=32,PrimaryColour=&H000000FF&,Outline=2,OutlineColour=&H00000000&,Alignment=10,MarginV=0'", 
        '-c:a', 'copy',  
        output_file
    ]
    subprocess.run(ffmpeg_command)

    # Optionally, check if ffmpeg process exits successfully
    print(f"Subtitled video created successfully: {output_file}")

# The full workflow

async def full_workflow():
    # Step 1: Generate the TTS audio
    await generate_speech_with_edge_tts(story_text, 'story_audio.mp3')

    # Step 2: Transcribe the audio into SRT subtitles using Whisper
    transcribe_audio_to_srt('story_audio.mp3', 'story_subtitles.srt')

    # Step 3: Create the video without subtitles
    create_video_without_subtitles("gameplay.mp4", "story_audio.mp3")

    # Step 4: Add subtitles to the video using ffmpeg
    add_styled_subtitles_with_ffmpeg("no_subtitles_output_video.mp4", "story_subtitles.srt", "subtitled_output_video.mp4", "Bangers")

# Run the full workflow
asyncio.run(full_workflow())
