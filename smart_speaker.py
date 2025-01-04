#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Голосовой помощник с поддержкой USB аудио устройств.

Модуль обеспечивает:
- Захват аудио с USB микрофона
- Распознавание речи через Google Speech Recognition
- Генерацию ответов через GPT
- Синтез речи через Google Text-to-Speech
- Воспроизведение аудио через ALSA

Требования:
- Python 3.7+
- USB аудио устройство
- Google Cloud credentials (файл ge200.json)
- Установленные библиотеки: google-cloud-speech, google-cloud-texttospeech,
  pyaudio, pygame, alsaaudio

Автор: Шабалин Игорь
Лицензия: MIT
Версия: 1.0
"""

from __future__ import division
import re
import sys
from google.cloud import speech
from google.cloud import texttospeech
import pyaudio
from six.moves import queue
import os
import pygame
import time
from gpt import ask
import warnings
import alsaaudio

# Конфигурационные параметры
RATE = 44100  # Частота дискретизации (Hz)
CHUNK = int(RATE / 10)  # Размер чанка (100ms)
MIN_TEXT_LENGTH = 3  # Минимальная длина текста для обработки
PAUSE_TIME = 1.5  # Минимальная пауза между обработками (сек)
LANGUAGE_CODE = "ru-RU"  # Язык распознавания
CREDENTIALS_FILE = "ge200.json"  # Файл с учетными данными Google Cloud
OUTPUT_FILE = "output.mp3"  # Файл для временного хранения аудио

# Настройка окружения
warnings.filterwarnings("ignore", category=RuntimeWarning)  # Игнорируем предупреждения ALSA
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"  # Скрываем приветствие pygame
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.getcwd(), CREDENTIALS_FILE)

class MicrophoneStream:
    """
    Класс для потоковой записи аудио с микрофона.
    
    Реализует контекстный менеджер для безопасной работы с аудиопотоком.
    Поддерживает работу с USB аудио устройствами через PyAudio.
    """
    
    def __init__(self, rate: int, chunk: int):
        """
        Инициализация параметров аудиопотока.
        
        Args:
            rate (int): Частота дискретизации
            chunk (int): Размер буфера
        """
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True
        
    def __enter__(self):
        """
        Инициализация аудио потока при входе в контекст.
        Настраивает и открывает поток с USB микрофона.
        """
        self._audio_interface = pyaudio.PyAudio()
        
        # Вывод информации о доступных устройствах
        self._print_audio_devices()
        
        try:
            self._audio_stream = self._audio_interface.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._rate,
                input=True,
                frames_per_buffer=self._chunk,
                stream_callback=self._fill_buffer,
                input_device_index=1  # USB микрофон
            )
            print("Аудио поток успешно открыт")
        except Exception as e:
            print(f"Ошибка при открытии аудио потока: {e}")
            raise
            
        self.closed = False
        return self

    def _print_audio_devices(self):
        """Вывод информации о доступных аудио устройствах."""
        print("\nДоступные аудио устройства:")
        for i in range(self._audio_interface.get_device_count()):
            dev_info = self._audio_interface.get_device_info_by_index(i)
            print(f"Device {i}: {dev_info['name']}")
            print(f"Max Input Channels: {dev_info['maxInputChannels']}")
            print(f"Default Sample Rate: {dev_info['defaultSampleRate']}")
            print("---")

    def __exit__(self, type_, value, traceback):
        """Корректное закрытие аудио потока."""
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Callback-функция для заполнения буфера аудиоданными."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """
        Генератор аудиоданных из буфера.
        
        Yields:
            bytes: Блок аудиоданных
        """
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]
            
            # Собираем все доступные чанки
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)

def text_message(message: str):
    """
    Обработка текстового сообщения.
    
    1. Отправляет сообщение в GPT
    2. Преобразует ответ в речь
    3. Воспроизводит аудиоответ
    
    Args:
        message (str): Текст для обработки
    """
    try:
        print("в GPT отправился следующий текст:", message)
        response = ask(111, message)
        print("от GPT получен ответ:", response)

        # Синтез речи
        tts_client = texttospeech.TextToSpeechClient()
        input_text = texttospeech.SynthesisInput(text=response)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=LANGUAGE_CODE,
            name='ru-RU-Wavenet-D',
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = tts_client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_config
        )

        # Управление микрофоном
        mixer = alsaaudio.Mixer(control='Mic', cardindex=1)
        
        try:
            mixer.setrec(0)  # Выключаем запись
            
            # Воспроизведение
            with open(OUTPUT_FILE, "wb") as out_file:
                out_file.write(response.audio_content)
            
            pygame.mixer.music.load(OUTPUT_FILE)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
        finally:
            mixer.setrec(1)  # Включаем запись обратно

    except Exception as err:
        print(f"Ошибка в text_message: {err}")
        try:
            mixer = alsaaudio.Mixer(control='Mic', cardindex=1)
            mixer.setrec(1)
        except:
            pass

def listen_print_loop(responses):
    """
    Обработка потока распознанной речи.
    
    Реализует логику обработки промежуточных и финальных результатов распознавания.
    
    Args:
        responses: Итератор с результатами распознавания от Google Speech
    """
    last_text = ""
    last_time = time.time()
    
    try:
        print("\nНачало прослушивания...")
        for response in responses:
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript.strip()
            is_final = result.is_final
            
            print(f"Промежуточный текст: {transcript}")
            print(f"is_final: {is_final}")
            
            if is_final:
                current_time = time.time()
                if current_time - last_time >= PAUSE_TIME:
                    if len(transcript) >= MIN_TEXT_LENGTH and not transcript.isspace():
                        print(f"Отправка текста в обработку: {transcript}")
                        text_message(transcript)
                        last_text = transcript
                        last_time = current_time
                    else:
                        print(f"Текст слишком короткий или пустой: '{transcript}'")
                else:
                    print(f"Слишком малое время с последней обработки: {current_time - last_time} сек")

            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Завершение работы...")
                break
                
    except Exception as e:
        print(f"Ошибка в listen_print_loop: {e}")

def initialize_audio():
    """Инициализация аудио подсистемы."""
    try:
        pygame.mixer.quit()
    except:
        pass
        
    try:
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        pygame.mixer.pre_init(44100, -16, 2, 4096)
        pygame.mixer.init(buffer=4096)
    except Exception as e:
        print(f"Ошибка инициализации аудио: {e}")
        pygame.mixer.init()  # Пробуем дефолтные настройки

def play_greeting():
    """Воспроизведение приветственного сообщения."""
    pygame.mixer.music.load("what_do_you_want.wav")
    
    try:
        mixer = alsaaudio.Mixer(control='Mic', cardindex=1)
        mixer.setrec(0)
        
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    finally:
        mixer.setrec(1)

def main():
    """
    Основная функция приложения.
    
    1. Инициализирует аудио подсистему
    2. Воспроизводит приветствие
    3. Запускает цикл распознавания речи
    """
    # Инициализация
    initialize_audio()
    play_greeting()
    
    # Настройка распознавания речи
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=LANGUAGE_CODE,
        enable_automatic_punctuation=True,
        model='command_and_search',
        use_enhanced=True
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True,
        single_utterance=False
    )

    # Запуск цикла распознавания
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)
        listen_print_loop(responses)

if __name__ == "__main__":
    main()
