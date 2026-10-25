/**
 * Browser MediaRecorder audio capture service for offline local speech-to-text.
 * Implements an explicit state machine: idle | recording | processing | error.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export type RecorderState = 'idle' | 'recording' | 'processing' | 'error';

export class AudioRecorderService {
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private stream: MediaStream | null = null;
  private state: RecorderState = 'idle';
  private mimeType: string = 'audio/webm';

  getState(): RecorderState {
    return this.state;
  }

  isRecording(): boolean {
    return this.state === 'recording';
  }

  async startRecording(): Promise<void> {
    if (this.state === 'recording' || this.state === 'processing') {
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this.state = 'error';
      throw new Error('Microphone access is not supported by your browser.');
    }

    this.state = 'processing';
    this.audioChunks = [];

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      this.mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/wav';

      this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: this.mimeType });

      this.mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onerror = () => {
        this.cleanup();
        this.state = 'error';
      };

      this.mediaRecorder.start(100); // 100ms slice
      this.state = 'recording';
    } catch (err: any) {
      this.cleanup();
      this.state = 'error';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        throw new Error('Microphone permission was denied. Please allow microphone access.');
      }
      throw new Error(err.message || 'Failed to initialize microphone.');
    }
  }

  async stopRecording(): Promise<Blob | null> {
    if (this.state !== 'recording' || !this.mediaRecorder) {
      this.cleanup();
      return null;
    }

    this.state = 'processing';

    return new Promise((resolve) => {
      if (!this.mediaRecorder) {
        this.cleanup();
        return resolve(null);
      }

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: this.mimeType });
        this.cleanup();
        resolve(audioBlob.size > 0 ? audioBlob : null);
      };

      try {
        if (this.mediaRecorder.state !== 'inactive') {
          this.mediaRecorder.stop();
        } else {
          this.cleanup();
          resolve(null);
        }
      } catch {
        this.cleanup();
        resolve(null);
      }
    });
  }

  cancelRecording(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      try {
        this.mediaRecorder.stop();
      } catch {
        // Safe ignore on abort
      }
    }
    this.cleanup();
  }

  cleanup(): void {
    if (this.stream) {
      try {
        this.stream.getTracks().forEach((track) => track.stop());
      } catch {
        // Safe ignore
      }
      this.stream = null;
    }
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.state = 'idle';
  }
}

export async function uploadAndTranscribeAudio(audioBlob: Blob): Promise<{ text: string; language: string }> {
  const formData = new FormData();
  const ext = audioBlob.type.includes('wav') ? 'wav' : audioBlob.type.includes('ogg') ? 'ogg' : 'webm';
  formData.append('file', audioBlob, `recording.${ext}`);

  const response = await fetch(`${API_BASE_URL}/api/v1/stt`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Transcription failed' }));
    throw new Error(errorData.detail || 'Failed to transcribe audio.');
  }

  return await response.json();
}
