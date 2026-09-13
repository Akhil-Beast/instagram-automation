import os
import sys
import time
import tempfile
import shutil
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Ensure console supports UTF-8 (emojis, etc.)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

class Analyzer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            print("Warning: GOOGLE_API_KEY not found. Analysis will be mocked or skipped.")
            
    def analyze_video(self, file_path):
        """
        Uploads the video to Gemini API, analyzes it for Topic, Caption, and Hashtags.
        """
        if not self.client:
            return {"topic": "Fitness Motivation", "caption": "Push your limits every day! 💪", "hashtags": "#fitness #gym #motivation"}
            
        print(f"Uploading {file_path} for analysis...")
        temp_dir = None
        try:
            # Create a temporary file with a sanitized name (no leading spaces) to satisfy HTTP headers
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, "video_analysis.mp4")
            shutil.copyfile(file_path, temp_file_path)

            video_file = self.client.files.upload(
                file=temp_file_path,
                config=types.UploadFileConfig(mime_type="video/mp4")
            )
            
            # Wait for processing
            while video_file.state.name == "PROCESSING":
                print("Waiting for video processing...")
                time.sleep(4)
                video_file = self.client.files.get(name=video_file.name)
                
            if video_file.state.name == "FAILED":
                raise Exception("Video processing failed on Gemini servers.")
                
            prompt = (
                "You are an elite Instagram growth strategist and social media manager specializing in "
                "Gym, Bodybuilding, Workout, and Fitness Motivation Reels.\n\n"
                "Analyze the provided video and produce:\n"
                "1. A concise Topic (2 to 4 words describing the exercise, workout style, or motivation theme).\n"
                "2. An engaging, high-converting Instagram caption with motivating tone and appropriate emojis.\n"
                "3. 5 to 10 highly relevant, targeted hashtags (e.g. #gymmotivation #fitnessgoals #bodybuilding).\n\n"
                "Respond in this EXACT format:\n"
                "Topic: [Your topic here]\n"
                "Caption: [Your caption here]\n"
                "Hashtags: [Your hashtags here]"
            )
            
            print(f"Generating content for {file_path}...")
            response = self.client.models.generate_content(
                model='gemini-3.6-flash',
                contents=[video_file, prompt]
            )
            
            raw_text = response.text or ""
            result = {
                "topic": "Gym Motivation",
                "caption": "Consistency is key. Push past your limits! 💪🔥",
                "hashtags": "#gymmotivation #workout #fitness #discipline"
            }
            
            import re
            m_topic = re.search(r'(?i)\*{0,2}Topic\*{0,2}\s*:\s*(.*?)(?=\n\*{0,2}(?:Caption|Hashtags)|\Z)', raw_text, re.DOTALL)
            m_caption = re.search(r'(?i)\*{0,2}Caption\*{0,2}\s*:\s*(.*?)(?=\n\*{0,2}Hashtags|\Z)', raw_text, re.DOTALL)
            m_hashtags = re.search(r'(?i)\*{0,2}Hashtags\*{0,2}\s*:\s*(.*?)$', raw_text, re.DOTALL)
            
            if m_topic and m_topic.group(1).strip():
                result["topic"] = m_topic.group(1).strip()
            if m_caption and m_caption.group(1).strip():
                result["caption"] = m_caption.group(1).strip()
            if m_hashtags and m_hashtags.group(1).strip():
                result["hashtags"] = m_hashtags.group(1).strip()
            
            # Cleanup file on Gemini cloud
            try:
                self.client.files.delete(name=video_file.name)
            except Exception:
                pass
            
            return result
            
        except Exception as e:
            print(f"Analysis failed for {file_path}: {e}")
            return {
                "topic": "Gym Motivation",
                "caption": "No excuses. Put in the work! 💪🔥",
                "hashtags": "#gymmotivation #fitness #workout #grind"
            }
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
