import random
import json
import whisper
from moviepy.editor import VideoFileClip, AudioFileClip
import asyncio
import os
import string
import re
from edge_tts import Communicate
import subprocess

with open('reddit_posts.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

selected_post = random.choice(posts)

abbreviations = {
    'aita': 'Am I the asshole',
    'aitb': 'Am I the bastard',
    'wibta': 'Would I be the asshole',
    'yta': 'You are the asshole',
    'nta': 'Not the asshole',
    'ynta': 'You are not the asshole',
    'yntb': 'You are not the bastard',
    'tl;dr': 'Too long; didn’t read',
    'btw': 'By the way',
    'ftw': 'For the win',
    'imo': 'In my opinion',
    'imho': 'In my humble opinion',
    'fwiw': 'For what it’s worth',
    'iirc': 'If I recall correctly'
}

age_gender_patterns = {
    r'(\d{1,2})[fF]': r'\1 female',  
    r'[fF](\d{1,2})': r'female \1',   
    r'(\d{1,2})[mM]': r'\1 male',   
    r'[mM](\d{1,2})': r'male \1'     
}

for abbrev, full in abbreviations.items():
    selected_post['text'] = selected_post['text'].lower().replace(abbrev, full)
    selected_post['title'] = selected_post['title'].lower().replace(abbrev, full)

for pattern, replacement in age_gender_patterns.items():
    selected_post['text'] = re.sub(pattern, replacement, selected_post['text'])
    selected_post['title'] = re.sub(pattern, replacement, selected_post['title'])

story_text = selected_post['text']
story_title = selected_post['title']

print(f"Selected Post: {story_title}")

model = whisper.load_model("base")

def remove_punctuation(text):
    return text.translate(str.maketrans('', '', string.punctuation))

def generate_srt(transcription, filename):
    srt_content = []
    counter = 1

    for segment in transcription:
        for word_info in segment['words']:
            word = word_info['word']
            word_no_punctuation = remove_punctuation(word) 
            start_time = word_info['start']
            end_time = word_info['end']
            
            start_srt_time = format_srt_time(start_time)
            end_srt_time = format_srt_time(end_time)
            
            srt_content.append(f"{counter}\n{start_srt_time} --> {end_srt_time}\n{word_no_punctuation.strip()}\n")
            counter += 1

    with open(filename, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_content))

def format_srt_time(seconds):
    ms = int((seconds % 1) * 1000)
    seconds = int(seconds)
    hrs = seconds // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

def transcribe_audio_to_srt(audio_file, srt_file):
    result = model.transcribe(audio_file, word_timestamps=True)

    transcription_segments = result['segments']

    generate_srt(transcription_segments, srt_file)

def split_text_into_segments(story_text, min_word_count_per_part=150):
    words = story_text.split()
    segments = []
    current_segment = []

    for word in words:
        current_segment.append(word)
        if len(current_segment) >= min_word_count_per_part:
            segments.append(' '.join(current_segment))
            current_segment = []

    if current_segment:
        segments.append(' '.join(current_segment))

    return segments


english_voices = [
    "en-AU-NatashaNeural", "en-AU-WilliamNeural", "en-CA-ClaraNeural", "en-CA-LiamNeural",
    "en-IE-ConnorNeural", "en-IE-EmilyNeural", "en-NZ-MitchellNeural", "en-NZ-MollyNeural",
    "en-GB-LibbyNeural", "en-GB-MaisieNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural",
    "en-GB-ThomasNeural", "en-US-AriaNeural", "en-US-AnaNeural", "en-US-ChristopherNeural",
    "en-US-EricNeural", "en-US-GuyNeural", "en-US-JennyNeural", "en-US-MichelleNeural",
    "en-US-RogerNeural", "en-US-SteffanNeural"
]

random_voice = random.choice(english_voices)

async def generate_speech_with_title(text, part_number, audio_filename='story_audio.mp3'):
    text_with_part = f"{story_title}, Part {part_number}. {text}"

    gen = Communicate(text_with_part, voice=random_voice)

    async for chunk in gen.stream():
        if chunk["type"] == "audio":
            with open(audio_filename, "ab") as audio_file:
                audio_file.write(chunk["data"])

def create_video_for_audio_part(gameplay_file, audio_file, part_number):
    try:
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration

        gameplay_clip = VideoFileClip(gameplay_file)
        gameplay_duration = gameplay_clip.duration

        max_start_time = gameplay_duration - audio_duration
        if max_start_time <= 0:
            start_time = 0
        else:
            start_time = random.uniform(0, max_start_time)

        video_segment_output = f"gameplay_segment_part_{part_number}.mp4"
        ffmpeg_command_1 = [
            'ffmpeg',
            '-y',
            '-ss', str(start_time), 
            '-i', gameplay_file,  
            '-t', str(audio_duration), 
            '-vf', 'scale=-1:1080,crop=608:1080',  
            '-r', '24',  
            '-an',  
            '-c:v', 'libx264', 
            video_segment_output  
        ]
        subprocess.run(ffmpeg_command_1, check=True)

        final_video_output = f"no_subtitles_output_video_part_{part_number}.mp4"
        ffmpeg_command_2 = [
            'ffmpeg',
            '-y', 
            '-i', video_segment_output,  
            '-i', audio_file,  
            '-map', '0:v:0', 
            '-map', '1:a:0', 
            '-c:v', 'copy', 
            '-c:a', 'copy', 
            '-shortest',  
            final_video_output  
        ]
        subprocess.run(ffmpeg_command_2, check=True)

        return final_video_output

    finally:
        try:
            audio_clip.close()
            gameplay_clip.close()
        except Exception as e:
            print(f"Error closing resources: {e}")
            
def add_subtitles_to_video(video_file, subtitle_file, part_number, font_path):
    output_file = f"final_part_{part_number}.mp4"
    ffmpeg_command = [
        'ffmpeg',
        '-i', video_file,
        '-vf', f"subtitles={subtitle_file}:force_style='FontName={font_path},FontSize=32,PrimaryColour=&HFFFFFF&,Outline=2,OutlineColour=&H00000000&,Alignment=10,MarginV=0'",
        '-c:a', 'copy',
        output_file
    ]
    subprocess.run(ffmpeg_command)
    return output_file

async def full_workflow():
    # Step 1: Split the story text into segments
    segment_texts = split_text_into_segments(story_text)
    num_segments = len(segment_texts)

    # List to store intermediate files for cleanup later
    intermediate_files = []

    # Step 2: Generate audio and create videos without subtitles for each part
    for i, segment_text in enumerate(segment_texts):
        part_number = i + 1
        audio_filename = f'story_audio_part_{part_number}.mp3'
        video_without_subtitles = f"no_subtitles_output_video_part_{part_number}.mp4"
        gameplay_segment_output = f"gameplay_segment_part_{part_number}.mp4"

        await generate_speech_with_title(segment_text, part_number, audio_filename)

        create_video_for_audio_part("gameplay.mp4", audio_filename, part_number)

        intermediate_files.extend([audio_filename, video_without_subtitles, gameplay_segment_output])

    # Step 3: Generate subtitles and burn into videos for each part
    for i in range(num_segments):
        part_number = i + 1
        audio_filename = f'story_audio_part_{part_number}.mp3'
        srt_filename = f'story_subtitles_part_{part_number}.srt'
        video_without_subtitles = f"no_subtitles_output_video_part_{part_number}.mp4"

        transcribe_audio_to_srt(audio_filename, srt_filename)

        # final_video_with_subtitles = add_subtitles_to_video(video_without_subtitles, srt_filename, part_number, "Bangers")
        final_video_with_subtitles = add_subtitles_to_video(video_without_subtitles, srt_filename, part_number, "Granby Elephant Pro")

        intermediate_files.append(srt_filename)

    for file in intermediate_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"Deleted intermediate file: {file}")


asyncio.run(full_workflow())