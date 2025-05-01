import os
import subprocess
import sys
import json
import wave
import vosk


def convert_audio(input_file, output_file="ukrainian_speech.wav"):
    """Convert audio to 16kHz, mono, 16-bit PCM WAV"""
    print(f"Converting {input_file} to proper format...")
    try:
        subprocess.call([
            'ffmpeg',
            '-i', input_file,
            '-ar', '16000',  # 16 kHz sample rate
            '-ac', '1',  # mono
            '-c:a', 'pcm_s16le',  # 16-bit PCM
            '-f', 'wav',  # WAV format
            '-y',  # Overwrite output file if it exists
            output_file
        ])
        print(f"Converted audio saved to {output_file}")
        return output_file
    except Exception as e:
        print(f"Error converting audio: {str(e)}")
        return None


def transcribe_audio(audio_path, model_path="vosk-model-uk-v3"):
    """Transcribe using Vosk"""
    if not os.path.exists(model_path):
        print(f"Error: Model path {model_path} does not exist")
        return None

    if not os.path.exists(audio_path):
        print(f"Error: Audio file {audio_path} does not exist")
        return None

    # Set up the model
    try:
        model = vosk.Model(model_path)
        print("Model loaded successfully")
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

    # Check audio format
    try:
        with wave.open(audio_path, "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
                print("Audio file is not in the correct format. Please convert it first.")
                return None

            # Print audio info
            print(f"Audio: channels={wf.getnchannels()}, sample width={wf.getsampwidth()}")
            print(f"Sample rate={wf.getframerate()}, frames={wf.getnframes()}")

            # Setup recognizer
            recognizer = vosk.KaldiRecognizer(model, wf.getframerate())

            # Process audio file
            results = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                    if text:
                        print(f"Partial: {text}")
                        results.append(text)

            # Get final result
            final_result = json.loads(recognizer.FinalResult())
            final_text = final_result.get("text", "")
            if final_text:
                print(f"FINAL: {final_text}")
                results.append(final_text)

            # Show overall results
            if results:
                complete_text = " ".join(results)
                print("\nComplete transcription:")
                print(complete_text)
                return complete_text
            else:
                print("No speech recognized in the audio file.")
                return ""

    except Exception as e:
        print(f"Error processing audio: {str(e)}")
        return None


# Main execution
if __name__ == "__main__":
    # Change this to your original audio file
    original_audio = "ukrainian_speech.mp3"

    # Convert audio to proper format
    converted_audio = convert_audio(original_audio)

    if converted_audio:
        # Transcribe the audio
        transcription = transcribe_audio(converted_audio)

        if transcription:
            # Save transcription to file
            with open("transcription.txt", "w", encoding="utf-8") as f:
                f.write(transcription)
            print("Transcription saved to transcription.txt")