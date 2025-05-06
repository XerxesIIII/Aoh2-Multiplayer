import pygame
import asyncio
import websockets
import av
import io
import time

async def receive_stream():
    try:
        async with websockets.connect(
            "ws://localhost:8765",
            ping_interval=30,
            ping_timeout=90,
            max_size=4 * 1024 * 1024
        ) as ws:
            pygame.init()
            screen = pygame.display.set_mode((1280, 720))
            pygame.display.set_caption("AoH2 Stream")
            clock = pygame.time.Clock()
            
            buffer = io.BytesIO()
            frame_count = 0
            start_time = time.time()
            container = None
            last_position = 0
            consecutive_errors = 0  
            
            while True:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    print(f"Received {len(data)} bytes (buffer size: {buffer.tell()})")
                    buffer.write(data)
                    
                    if not container and buffer.tell() > 1024 * 1024: 
                        buffer.seek(0)
                        try:
                            container = av.open(buffer, mode='r', format='mpegts')
                            stream = container.streams.video[0]
                            print("Initialized AV container")
                            last_position = 0
                            consecutive_errors = 0
                        except av.error.InvalidDataError as e:
                            print(f"Failed to open container: {str(e)}")
                            buffer.seek(0)
                            buffer.truncate(0)
                            last_position = 0
                            continue
                    
                    if container:
                        buffer.seek(last_position)
                        try:
                            for packet in container.demux(stream):
                                try:
                                    for frame in packet.decode():
                                        rgb_frame = frame.to_rgb()
                                        img = rgb_frame.to_image()
                                        mode = img.mode
                                        size = img.size
                                        data = img.tobytes()
                                        surface = pygame.image.frombuffer(data, size, mode)
                                        screen.blit(surface, (0, 0))
                                        pygame.display.flip()
                                        frame_count += 1
                                        consecutive_errors = 0
                                        if frame_count % 100 == 0:
                                            elapsed = time.time() - start_time
                                            print(f"Processed {frame_count} frames in {elapsed:.2f} seconds ({frame_count/elapsed:.2f} FPS)")
                                        clock.tick(20)
                                except (av.error.InvalidDataError, av.error.EOFError) as e:
                                    print(f"Packet decoding error: {str(e)}")
                                    consecutive_errors += 1
                                    if consecutive_errors > 5:
                                        print("Too many consecutive errors, resetting buffer")
                                        container.close()
                                        container = None
                                        buffer.seek(0)
                                        buffer.truncate(0)
                                        last_position = 0
                                        consecutive_errors = 0
                                        break
                            last_position = buffer.tell()
                            if buffer.tell() > 8 * 1024 * 1024:  # Clear buffer if too large
                                remaining = buffer.read()[last_position:]
                                buffer.seek(0)
                                buffer.truncate(0)
                                buffer.write(remaining)
                                last_position = 0
                                if container:
                                    container.close()
                                    container = None
                                    print("Reinitializing AV container due to large buffer")
                        except (av.error.InvalidDataError, av.error.EOFError) as e:
                            print(f"Demux error: {str(e)}")
                            consecutive_errors += 1
                            if consecutive_errors > 5:
                                print("Too many demux errors, resetting buffer")
                                container.close()
                                container = None
                                buffer.seek(0)
                                buffer.truncate(0)
                                last_position = 0
                                consecutive_errors = 0
                            continue
                    
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            return
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"WebSocket connection closed: {str(e)}")
                    break
    except Exception as e:
        print(f"Connection error: {str(e)}")
    finally:
        pygame.quit()
        if 'container' in locals() and container:
            container.close()

if __name__ == "__main__":
    asyncio.run(receive_stream())