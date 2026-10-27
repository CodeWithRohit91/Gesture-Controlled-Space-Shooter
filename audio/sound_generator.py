"""
Procedural Sound Generation Module for GestureStrike.
Generates all retro-modern sci-fi sound effects and looping background beats
using mathematical waveforms in NumPy, rendered through Pygame's sndarray mixer.
Zero external audio files required!
"""

import math
import pygame
import numpy as np
from config import AUDIO_SAMPLE_RATE, DEFAULT_SFX_VOLUME, DEFAULT_MUSIC_VOLUME


class SoundManager:
    """
    Manages procedural audio synthesis, playback, volume, and muting.
    All sounds are synthesized at startup into Pygame Sound buffers.
    """

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.muted = False
        self.sfx_volume = DEFAULT_SFX_VOLUME
        self.music_volume = DEFAULT_MUSIC_VOLUME
        self.sounds = {}
        self.music_channel = None

        # Initialize mixer if not already initialized
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=sample_rate, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(16)
            self.music_channel = pygame.mixer.Channel(0)
            self._generate_all_sounds()
        except Exception as e:
            print(f"[SoundManager] Warning: Audio mixer failed to initialize ({e}). Audio disabled.")

    def _to_stereo(self, mono_array: np.ndarray) -> pygame.mixer.Sound:
        """Converts float numpy array [-1.0, 1.0] to 16-bit signed stereo Pygame Sound."""
        # Clip to prevent distortion
        clipped = np.clip(mono_array, -0.98, 0.98)
        int16_samples = (clipped * 32767).astype(np.int16)
        stereo = np.column_stack((int16_samples, int16_samples))
        return pygame.sndarray.make_sound(stereo)

    def _generate_all_sounds(self):
        """Pre-renders all game sound effects and the background beat."""
        self.sounds["shoot"] = self._generate_laser(freq_start=880, freq_end=240, duration=0.12)
        self.sounds["triple_shoot"] = self._generate_triple_laser(duration=0.15)
        self.sounds["enemy_hit"] = self._generate_hit(duration=0.08)
        self.sounds["explosion"] = self._generate_explosion(duration=0.35, pitch_decay=True)
        self.sounds["bomb_blast"] = self._generate_bomb_blast(duration=1.2)
        self.sounds["powerup"] = self._generate_powerup(duration=0.32)
        self.sounds["shield_activate"] = self._generate_shield_hum(duration=0.25)
        self.sounds["shield_hit"] = self._generate_shield_deflect(duration=0.15)
        self.sounds["player_hit"] = self._generate_player_hurt(duration=0.3)
        self.sounds["boss_warning"] = self._generate_boss_siren(duration=1.2)
        self.sounds["boss_hit"] = self._generate_boss_hit(duration=0.2)
        self.sounds["ui_blip"] = self._generate_ui_blip(duration=0.04)

        # Generate looping background beat
        self.bg_loop = self._generate_synthwave_beat(bpm=124, bars=2)
        self.apply_volumes()

    def _generate_laser(self, freq_start: float, freq_end: float, duration: float) -> pygame.mixer.Sound:
        """Sci-fi laser blaster with logarithmic frequency drop and sharp attack."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        # Exponential frequency slide
        freqs = freq_start * (freq_end / freq_start) ** (t / duration)
        phases = 2 * np.pi * np.cumsum(freqs) / self.sample_rate
        # Waveform: mix of sine and square wave for that crisp 80s arcade feel
        wave = 0.7 * np.sin(phases) + 0.3 * np.sign(np.sin(phases))
        # Exponential volume envelope
        envelope = np.exp(-t * 22)
        return self._to_stereo(wave * envelope * 0.75)

    def _generate_triple_laser(self, duration: float) -> pygame.mixer.Sound:
        """Dual-frequency harmonic plasma spread shot with subtle chorus."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        freq1 = 1100 * (300 / 1100) ** (t / duration)
        freq2 = 1450 * (400 / 1450) ** (t / duration)
        wave1 = np.sin(2 * np.pi * np.cumsum(freq1) / self.sample_rate)
        wave2 = np.sin(2 * np.pi * np.cumsum(freq2) / self.sample_rate)
        envelope = np.exp(-t * 18)
        return self._to_stereo((0.5 * wave1 + 0.5 * wave2) * envelope * 0.8)

    def _generate_hit(self, duration: float) -> pygame.mixer.Sound:
        """Quick percussive blip on enemy bullet impact."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        freq = 350 * np.exp(-t * 30)
        sine = np.sin(2 * np.pi * freq * t)
        noise = np.random.uniform(-0.4, 0.4, n_samples)
        envelope = np.exp(-t * 40)
        return self._to_stereo((sine * 0.7 + noise * 0.3) * envelope * 0.7)

    def _generate_explosion(self, duration: float, pitch_decay: bool = True) -> pygame.mixer.Sound:
        """Crisp white noise explosion with decaying low-pass rumble."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        noise = np.random.uniform(-1.0, 1.0, n_samples)
        # Low frequency rumble
        rumble = np.sin(2 * np.pi * 65 * np.exp(-t * 4) * t)
        # Envelope: sharp attack, smooth exponential decay
        envelope = np.exp(-t * 9)
        combined = (0.65 * noise + 0.35 * rumble) * envelope
        return self._to_stereo(combined * 0.85)

    def _generate_bomb_blast(self, duration: float) -> pygame.mixer.Sound:
        """Massive EMP shockwave: deep sub-bass drop, roaring noise, and lingering resonance."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        # Sub-bass slide 180 Hz down to 25 Hz
        sub = np.sin(2 * np.pi * (180 * np.exp(-t * 3.5)) * t)
        noise = np.random.uniform(-1.0, 1.0, n_samples)
        # Resonant ring at 440 Hz decaying
        ring = np.sin(2 * np.pi * 440 * t) * np.exp(-t * 6)
        envelope = np.exp(-t * 2.8)
        combined = (0.5 * sub + 0.4 * noise + 0.2 * ring) * envelope
        return self._to_stereo(combined * 0.95)

    def _generate_powerup(self, duration: float) -> pygame.mixer.Sound:
        """Ascending sci-fi arpeggio (C5 -> E5 -> G5 -> C6) with crystalline sparkle."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        notes = [523.25, 659.25, 783.99, 1046.50]  # C5, E5, G5, C6
        note_len = duration / len(notes)
        wave = np.zeros(n_samples)

        for i, freq in enumerate(notes):
            start_idx = int(i * note_len * self.sample_rate)
            end_idx = int((i + 1) * note_len * self.sample_rate) if i < len(notes) - 1 else n_samples
            segment_t = t[start_idx:end_idx] - (i * note_len)
            sub_len = len(segment_t)
            segment_env = np.exp(-segment_t * 8)
            # Add harmonic overtones
            sub_wave = (
                0.7 * np.sin(2 * np.pi * freq * segment_t) +
                0.3 * np.sin(2 * np.pi * (freq * 2) * segment_t)
            ) * segment_env
            wave[start_idx:start_idx + sub_len] = sub_wave

        return self._to_stereo(wave * 0.8)

    def _generate_shield_hum(self, duration: float) -> pygame.mixer.Sound:
        """Resonant frequency sweep up when activating plasma shield."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        freq = 200 + 400 * (t / duration)
        wave = np.sin(2 * np.pi * freq * t) * (1.0 + 0.3 * np.sin(2 * np.pi * 20 * t))
        envelope = np.sin(np.pi * (t / duration)) ** 0.5
        return self._to_stereo(wave * envelope * 0.7)

    def _generate_shield_deflect(self, duration: float) -> pygame.mixer.Sound:
        """High-pitched metallic deflection ping."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        wave = (
            0.6 * np.sin(2 * np.pi * 1760 * t) +
            0.4 * np.sin(2 * np.pi * 2640 * t)
        ) * np.exp(-t * 28)
        return self._to_stereo(wave * 0.75)

    def _generate_player_hurt(self, duration: float) -> pygame.mixer.Sound:
        """Low punch impact with distortion crunch."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        thump = np.sin(2 * np.pi * 90 * np.exp(-t * 12) * t)
        noise = np.random.uniform(-0.8, 0.8, n_samples)
        envelope = np.exp(-t * 10)
        return self._to_stereo((0.7 * thump + 0.5 * noise) * envelope * 0.85)

    def _generate_boss_siren(self, duration: float) -> pygame.mixer.Sound:
        """Dual-tone urgent alarm siren announcing the arrival of the Dreadnought."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        # 3Hz alternating siren between 440 Hz and 660 Hz
        mod = 0.5 * (1 + np.sin(2 * np.pi * 3.5 * t))
        freqs = 440 + 220 * mod
        phases = 2 * np.pi * np.cumsum(freqs) / self.sample_rate
        saw = 2 * (phases / (2 * np.pi) - np.floor(phases / (2 * np.pi) + 0.5))
        sine = np.sin(phases)
        envelope = np.ones(n_samples)
        # Fade out end
        fade_len = int(self.sample_rate * 0.15)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
        return self._to_stereo((0.6 * sine + 0.4 * saw) * envelope * 0.8)

    def _generate_boss_hit(self, duration: float) -> pygame.mixer.Sound:
        """Heavy mechanical armor impact."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        thud = np.sin(2 * np.pi * 120 * np.exp(-t * 15) * t)
        spark = np.random.uniform(-0.5, 0.5, n_samples) * np.exp(-t * 30)
        return self._to_stereo((0.7 * thud + 0.3 * spark) * 0.8)

    def _generate_ui_blip(self, duration: float) -> pygame.mixer.Sound:
        """Clean high-pitch UI tick for navigation and button hovering."""
        n_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, n_samples, False)
        wave = np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 60)
        return self._to_stereo(wave * 0.5)

    def _generate_synthwave_beat(self, bpm: int = 124, bars: int = 2) -> pygame.mixer.Sound:
        """
        Procedurally synthesized 4-on-the-floor synthwave rhythm:
        - Deep punchy 808-style kicks on every beat.
        - Snappy snare/clap on beats 2 and 4.
        - High-frequency closed hi-hat ticking on 16th notes.
        - Driving synth bass sequence pumping in key of A minor.
        """
        beats_per_bar = 4
        total_beats = bars * beats_per_bar
        seconds_per_beat = 60.0 / bpm
        total_duration = total_beats * seconds_per_beat
        n_samples = int(self.sample_rate * total_duration)
        t = np.linspace(0, total_duration, n_samples, False)

        track = np.zeros(n_samples)

        # 1. KICK DRUM on every quarter note (beats 0, 1, 2, 3...)
        kick_dur = 0.22
        kick_samples = int(self.sample_rate * kick_dur)
        kick_t = np.linspace(0, kick_dur, kick_samples, False)
        kick_wave = np.sin(2 * np.pi * (140 * np.exp(-kick_t * 24)) * kick_t) * np.exp(-kick_t * 14)

        for b in range(total_beats):
            idx = int(b * seconds_per_beat * self.sample_rate)
            end_idx = min(idx + kick_samples, n_samples)
            part_len = end_idx - idx
            track[idx:end_idx] += kick_wave[:part_len] * 0.9

        # 2. SNARE on beats 2 and 4 (1 and 3 in 0-indexed count: 1, 3, 5, 7...)
        snare_dur = 0.18
        snare_samples = int(self.sample_rate * snare_dur)
        snare_t = np.linspace(0, snare_dur, snare_samples, False)
        snare_noise = np.random.uniform(-0.8, 0.8, snare_samples) * np.exp(-snare_t * 22)
        snare_tone = np.sin(2 * np.pi * 210 * snare_t) * np.exp(-snare_t * 18)
        snare_wave = snare_noise * 0.7 + snare_tone * 0.3

        for b in range(total_beats):
            if b % 2 == 1:
                idx = int(b * seconds_per_beat * self.sample_rate)
                end_idx = min(idx + snare_samples, n_samples)
                part_len = end_idx - idx
                track[idx:end_idx] += snare_wave[:part_len] * 0.65

        # 3. HI-HAT on 16th notes
        hihat_dur = 0.04
        hihat_samples = int(self.sample_rate * hihat_dur)
        hihat_t = np.linspace(0, hihat_dur, hihat_samples, False)
        hihat_wave = np.random.uniform(-0.4, 0.4, hihat_samples) * np.exp(-hihat_t * 90)

        sixteenths = total_beats * 4
        sixteenth_dur = seconds_per_beat / 4.0
        for s in range(sixteenths):
            vol = 0.35 if s % 2 == 1 else 0.20  # accent off-beats
            idx = int(s * sixteenth_dur * self.sample_rate)
            end_idx = min(idx + hihat_samples, n_samples)
            part_len = end_idx - idx
            track[idx:end_idx] += hihat_wave[:part_len] * vol

        # 4. ROLLING BASSLINE (A minor: A1 55Hz, C2 65.4Hz, D2 73.4Hz, E2 82.4Hz)
        bass_notes = [55.0, 55.0, 65.4, 55.0, 73.4, 65.4, 55.0, 82.4]  # 8 eighth notes per bar
        eighth_dur = seconds_per_beat / 2.0
        total_eighths = total_beats * 2

        for e in range(total_eighths):
            freq = bass_notes[e % len(bass_notes)]
            dur = eighth_dur * 0.85
            dur_samples = int(self.sample_rate * dur)
            bass_t = np.linspace(0, dur, dur_samples, False)
            # Sawtooth + sine for synth bass warmth
            phases = 2 * np.pi * freq * bass_t
            saw = 2 * (phases / (2 * np.pi) - np.floor(phases / (2 * np.pi) + 0.5))
            sine = np.sin(phases)
            bass_env = np.exp(-bass_t * 6)
            bass_wave = (0.5 * saw + 0.5 * sine) * bass_env

            idx = int(e * eighth_dur * self.sample_rate)
            end_idx = min(idx + dur_samples, n_samples)
            part_len = end_idx - idx
            track[idx:end_idx] += bass_wave[:part_len] * 0.45

        return self._to_stereo(track * 0.7)

    def play(self, sound_name: str):
        """Plays a one-shot sound effect if audio is not muted."""
        if self.muted or sound_name not in self.sounds:
            return
        sound = self.sounds.get(sound_name)
        if sound:
            sound.play()

    def start_music(self):
        """Starts looping the procedural synthwave background beat."""
        if self.music_channel and hasattr(self, "bg_loop") and self.bg_loop:
            if not self.music_channel.get_busy():
                self.music_channel.play(self.bg_loop, loops=-1)
                self.apply_volumes()

    def stop_music(self):
        """Stops the background music."""
        if self.music_channel:
            self.music_channel.stop()

    def toggle_mute(self) -> bool:
        """Toggles audio mute on or off. Returns new mute state."""
        self.muted = not self.muted
        self.apply_volumes()
        return self.muted

    def apply_volumes(self):
        """Applies volume settings to all channels and sounds."""
        effective_sfx = 0.0 if self.muted else self.sfx_volume
        effective_music = 0.0 if self.muted else self.music_volume

        for s in self.sounds.values():
            s.set_volume(effective_sfx)

        if self.music_channel:
            self.music_channel.set_volume(effective_music)
