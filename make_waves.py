import ffmpeg

def make_waveform_clip(audio_path, out_path, width=1920, height=300,
                        color="0xFFD700"):
    input_file = ffmpeg.input(audio_path)
    
    # Create waveform video from audio
    v = input_file.filter("showwaves", s=f"{width}x{height}", mode="cline",
                          colors=color, rate=30)
    
    # Get audio stream from input
    a = input_file.audio
    
    # Combine video and audio in output
    out = ffmpeg.output(v, a, out_path, 
                        pix_fmt="yuva420p" if out_path.endswith(".mov") else "yuv420p",
                        vcodec="libx264", acodec="aac")
    ffmpeg.run(out, overwrite_output=True)

make_waveform_clip("lecture.wav", "waveform.mp4", color = "0x219ebc")