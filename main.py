"""
GestureStrike - Main Application Entry Point
A polished, college-grade space shooter controlled in real-time by webcam hand gestures.
Pair programming project built with Pygame, OpenCV, MediaPipe Hands, and NumPy.
"""

import sys
import os
import pygame

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    FPS,
    WINDOW_TITLE,
    COLOR_PRIMARY_CYAN,
    COLOR_PRIMARY_BLUE,
    COLOR_ACCENT_MAGENTA
)
from audio.sound_generator import SoundManager
from vision.hand_tracker import HandTracker
from game.scenes import SceneManager


def create_window_icon() -> pygame.Surface:
    """Creates a procedural sci-fi starship icon for the operating system window."""
    icon_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
    pts = [(16, 2), (2, 28), (10, 22), (16, 25), (22, 22), (30, 28)]
    pygame.draw.polygon(icon_surf, COLOR_PRIMARY_CYAN, pts)
    pygame.draw.polygon(icon_surf, (255, 255, 255), pts, width=1)
    pygame.draw.circle(icon_surf, COLOR_ACCENT_MAGENTA, (16, 14), 3)
    return icon_surf


def main():
    """Main program execution loop."""
    print("==================================================")
    print(" GESTURESTRIKE - AI HAND-CONTROLLED SPACE SHOOTER ")
    print("==================================================")
    print("Initializing Pygame subsystems...")

    pygame.init()
    pygame.font.init()

    # Create Pygame Display Window
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    try:
        pygame.display.set_icon(create_window_icon())
    except Exception as e:
        print(f"[Main] Note: Could not set window icon ({e}).")

    clock = pygame.time.Clock()

    # Initialize Procedural Sound Manager
    print("Generating procedural audio synthesizers...")
    sounds = SoundManager()

    # Initialize Multithreaded Hand Tracking Engine
    print("Starting asynchronous MediaPipe Hands tracker thread...")
    tracker = HandTracker()

    # Initialize Scene Manager
    print("Loading game scenes and assets...")
    scenes = SceneManager(tracker=tracker, sounds=sounds)

    print("GestureStrike running at 60 FPS! Ready for player input.")
    print("Tip: Press [K] to toggle Keyboard Mode | Press [M] to toggle Audio Mute.")

    running = True
    try:
        while running:
            # High-precision delta time (capped to prevent physics tunneling on lag spikes)
            raw_dt = clock.tick(FPS)
            dt = min(raw_dt / 1000.0, 0.05)

            # Event Handling Loop
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    scenes.handle_event(event)

            # Simulation & Physics Update
            scenes.update(dt)

            # Graphics Rendering
            scenes.draw(screen)

            # Flip Back-Buffer to Screen
            pygame.display.flip()

    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user. Exiting gracefully...")
    except Exception as e:
        print(f"\n[Main] Unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Guaranteed cleanup of background threads and camera resources
        print("[Main] Releasing webcam and shutting down worker threads...")
        tracker.stop()
        sounds.stop_music()
        pygame.quit()
        print("[Main] GestureStrike shutdown complete. Goodbye, Pilot!")


if __name__ == "__main__":
    main()
