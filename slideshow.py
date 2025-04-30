
#!/usr/bin/python3
import os
import random
import math
from moviepy import ImageClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips
from PIL import Image
import numpy as np
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a music-driven slideshow.")
    parser.add_argument('--song_file', type=str, required=True, help="Path to the song file.")
    parser.add_argument('--song_template', type=str, required=True, help="Path to the song template file.")
    parser.add_argument('--output_path', type=str, required=True, help="Path to the Ouput directory.")
    return parser.parse_args()

def parse_template(file_path):
    config = {}
    with open(file_path, encoding='utf-8-sig') as file:
        for line in file:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            key, value = map(str.strip, line.split(':', 1))
            if key == 'Singers Images':
                value = [img.strip() for img in value.split(',')]
            config[key] = value
    return config

class SlideShowGenerator:
    def __init__(self, music_path, output_path, song_info=None):
        self.music_path = music_path
        self.output_path = output_path
        self.frame_path = os.path.join(output_path, song_info['Song'] + '.jpg')
        self.video_path = os.path.join(output_path, song_info['Song'] + '.mp4')
        self.width = 1920
        self.height = 1080
        self.footer_height = 120
        self.song_info = song_info or {
            'Song': 'Unknown Title',
            'Film': 'Unknown Album',
            'Singers (Original)': 'Unknown Artists',
            'Singers (Karaoke)': 'Unknown Singer',
            'Singers Images': [],
            'Poster Image': None
        }

        # Validate inputs
        if not os.path.exists(music_path):
            raise ValueError(f"Music file {music_path} does not exist")
        if not self.song_info['Singers Images']:
            raise ValueError("No singer images provided in the template")
        if not os.path.exists(self.song_info['Poster Image']):
            raise ValueError(f"Poster image file {self.song_info['Poster Image']} does not exist")

    def _create_slide_with_footer(self, image_path, slide_duration):
        """
        Create a single slide with footer integrated
        """
        # Process the image
        with Image.open(image_path) as img:
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Calculate resize dimensions
            img_ratio = img.width / img.height
            target_ratio = self.width / self.height
            
            if img_ratio > target_ratio:
                new_width = self.width
                new_height = int(self.width / img_ratio)
            else:
                new_height = self.height
                new_width = int(self.height * img_ratio)
                
            # Resize image
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Create background with footer space
            background = Image.new('RGB', (self.width, self.height), 'black')
            
            # Paste main image
            paste_x = (self.width - new_width) // 2
            paste_y = (self.height - new_height) // 2
            background.paste(img_resized, (paste_x, paste_y))
            
            # Create semi-transparent gradient for footer
            footer = Image.new('RGBA', (self.width, self.footer_height), (0, 0, 0, 0))
            for y in range(self.footer_height):
                alpha = int((y / self.footer_height) ** 1.5 * 160)
                for x in range(self.width):
                    footer.putpixel((x, y), (0, 0, 0, alpha))
            
            # Paste footer at bottom
            background.paste((0, 0, 0), (0, self.height - self.footer_height),
                           mask=footer.convert('L'))
            
            # Convert to array for MoviePy
            slide = np.array(background)
        
        # Create base clip
        clip = ImageClip(slide, duration=slide_duration)
        
        # Add text overlays
        font_size = 24
        line_height = 26
        left_margin = 40
        text_lines = [f"{key}: {value}" for key, value in self.song_info.items() if "Image" not in key]
        
        text_clips = []
        for i, line in enumerate(text_lines):
            text_clip = TextClip(
                text=line,
                font='C:\Windows\Fonts\Arial.ttf',
                font_size=font_size,
                color='white',
                stroke_color='black',
                stroke_width=1,
                duration=slide_duration
            )
            
            y_pos = self.height - self.footer_height + 10 + (i * line_height)
            text_clips.append(text_clip.with_position((left_margin, y_pos)))

        return CompositeVideoClip([clip] + text_clips)

    def create_music_driven_slideshow(self, slide_duration=3, capture_time=10):
        # Get image files from the template
        image_files = self.song_info['Singers Images']
        if not all(os.path.exists(img) for img in image_files):
            raise ValueError("One or more singer image files do not exist")

        # Add the poster image as the first slide
        extended_image_list = [self.song_info['Poster Image']]

        # Calculate the number of slides needed
        audio = AudioFileClip(self.music_path)
        total_duration = audio.duration
        slides_needed = math.ceil(total_duration / slide_duration)

        # Create a repeating sequence of images
        repeats_needed = math.ceil(slides_needed / len(image_files))
        for _ in range(repeats_needed):
            shuffled_images = image_files.copy()
            random.shuffle(shuffled_images)
            extended_image_list.extend(shuffled_images)
        extended_image_list = extended_image_list[:slides_needed]

        # Create video clips with integrated footer
        clips = [
            self._create_slide_with_footer(img_path, slide_duration)
            for img_path in extended_image_list
        ]

        # Concatenate all clips
        final_clip = concatenate_videoclips(
            clips=clips,
            method='chain',
        )

        # Trim to match audio duration
        if final_clip.duration > total_duration:
            final_clip = final_clip.with_duration(total_duration)

        # Capture frame if requested
        if capture_time < final_clip.duration:
            frame = final_clip.get_frame(capture_time)
            Image.fromarray(frame).save(self.frame_path, quality=95)

        # Add audio
        final_clip = final_clip.with_audio(audio)

        # Write final video
        final_clip.write_videofile(
            self.video_path,
            codec='libx264',
            audio_codec='aac',
            fps=30
        )

        # Clean up
        final_clip.close()
        audio.close()

        return self.video_path, self.frame_path

def main():
    args = parse_args()
    song_info = parse_template(args.song_template)

    generator = SlideShowGenerator(
        music_path=args.song_file,
        song_info=song_info,
        output_path=args.output_path
    )
    
    video_path, frame_path = generator.create_music_driven_slideshow(
        slide_duration=30,
        capture_time=10
    )
    
    print(f"HD slideshow created: {video_path}")
    print(f"Frame captured at 10s: {frame_path}")

if __name__ == '__main__':
    main()