import subprocess
import asyncio
import websockets
import os

async def stream_game(websocket):
    try:
        print("Streaming started!")
        ffmpeg_path = "C:/ffmpeg/bin/ffmpeg.exe" 
        
        ffmpeg_cmd = [
            ffmpeg_path,
            "-f", "gdigrab",
            "-i", "title=Age of Civilizations II",
            "-vf", "fps=40,scale=1280:720",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-b:v", "4000k",
            "-g", "40",  # Keyframe 
            "-force_key_frames", "expr:gte(t,n_forced*2)",  
            "-flush_packets", "1",  #
            "-rtbufsize", "2M",  # Limit real-time buffer size
            "-f", "mpegts",
            "pipe:1"
        ]
        
        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
        except FileNotFoundError as e:
            print(f"FFmpeg not found: {str(e)}. Ensure FFmpeg is installed and the path is correct.")
            return
        except Exception as e:
            print(f"Failed to start FFmpeg: {str(e)}")
            return
        
        # Read FFmpeg stderr 
        stderr_output = []
        async def read_stderr():
            while True:
                line = await asyncio.get_event_loop().run_in_executor(None, process.stderr.readline)
                if not line:
                    break
                stderr_output.append(line.decode())
                print(f"FFmpeg stderr: {line.decode().strip()}")
        
        asyncio.create_task(read_stderr())
        
        chunk_size = 128 * 1024  #128KB
        chunk_count = 0
        total_bytes = 0
        
        while True:
            data = process.stdout.read(chunk_size)
            if not data:
                print("FFmpeg stdout closed")
                break
            try:
                await websocket.send(data)
                chunk_count += 1
                total_bytes += len(data)
                if chunk_count % 1000 == 0:
                    print(f"Sent {chunk_count} chunks ({total_bytes / 1024 / 1024:.2f} MB)")
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket connection closed by client")
                break
            except Exception as e:
                print(f"WebSocket send error: {str(e)}")
                break
                
        if stderr_output:
            print("FFmpeg errors encountered:")
            for line in stderr_output:
                print(line.strip())
                
    except Exception as e:
        print(f"Stream error: {str(e)}")
    finally:
        if 'process' in locals():
            process.terminate()
        print("Stream ended")

async def handle_connection(websocket, path):
    print(f"Connection established, path: {path}")
    await stream_game(websocket)

async def main():
    try:
        server = await websockets.serve(
            handle_connection,
            "0.0.0.0",
            8765,
            ping_interval=30,  
            ping_timeout=90
        )
        print("Server ready at ws://0.0.0.0:8765")
        await server.wait_closed()
    except Exception as e:
        print(f"Server error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")