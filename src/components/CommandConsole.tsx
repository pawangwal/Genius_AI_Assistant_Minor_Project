import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Send, WifiOff, Loader2, Mic, MicOff, Wrench, AlertCircle } from 'lucide-react';
import { useInterface } from '../context/InterfaceContext';
import { useStore } from '../store/useStore';
import { AudioRecorderService, uploadAndTranscribeAudio } from '../services/audioRecorder';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const CommandConsole: React.FC = () => {
  const { isListening, setIsListening } = useInterface();
  const { messages, addMessage } = useStore();
  const [inputText, setInputText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<string | null>(null);

  const consoleRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<AudioRecorderService>(new AudioRecorderService());

  // Check backend server readiness probe periodically
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/health/ready`);
        const data = await response.json();
        if (response.ok && data.status === 'ready') {
          setIsConnected(true);
          setConnectionError(null);
        } else {
          setIsConnected(false);
          const dbStatus = data.dependencies?.database || 'disconnected';
          setConnectionError(`Backend degraded: Database ${dbStatus}`);
        }
      } catch (error) {
        setIsConnected(false);
        setConnectionError('Unable to connect to FastAPI backend (http://127.0.0.1:8000).');
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll console
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [messages, activeTool]);

  // Client-side Text-to-Speech with Hindi auto-detection
  const speakText = (text: string) => {
    if (!window.speechSynthesis) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);

    // Detect if Hindi text (Devanagari Unicode block)
    if (/[ऀ-ॿ]/.test(text)) {
      const voices = window.speechSynthesis.getVoices();
      const hindiVoice = voices.find((v) => v.lang.includes('hi') || v.name.includes('Hindi'));
      if (hindiVoice) {
        utterance.voice = hindiVoice;
        utterance.lang = 'hi-IN';
      } else {
        utterance.lang = 'hi-IN';
      }
    } else {
      utterance.lang = 'en-US';
    }

    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  };

  const wasListeningRef = useRef(false);

  // Component unmount cleanup
  useEffect(() => {
    return () => {
      recorderRef.current.cleanup();
    };
  }, []);

  // Browser MediaRecorder voice capture flow
  useEffect(() => {
    let isCancelled = false;

    const handleVoiceCapture = async () => {
      // Transition from idle -> listening
      if (isListening && !wasListeningRef.current) {
        wasListeningRef.current = true;
        try {
          await recorderRef.current.startRecording();
        } catch (err: any) {
          wasListeningRef.current = false;
          setIsListening(false);
          addMessage(err.message || 'Microphone access denied.', 'assistant');
        }
      } else if (!isListening && wasListeningRef.current) {
        // Transition from listening -> stop
        wasListeningRef.current = false;
        try {
          const audioBlob = await recorderRef.current.stopRecording();
          if (!isCancelled && audioBlob && audioBlob.size > 0) {
            setIsLoading(true);
            addMessage('Transcribing audio locally...', 'assistant');

            const result = await uploadAndTranscribeAudio(audioBlob);
            if (result.text && result.text.trim()) {
              addMessage(result.text, 'user');
              await executeChatCompletion(result.text);
            } else {
              addMessage('No speech detected. Please try again.', 'assistant');
              setIsLoading(false);
            }
          }
        } catch (err: any) {
          if (!isCancelled) {
            addMessage(`Voice transcription error: ${err.message}`, 'assistant');
            setIsLoading(false);
          }
        }
      }
    };

    handleVoiceCapture();
    return () => {
      isCancelled = true;
    };
  }, [isListening]);

  // Execute chat with SSE Streaming and tool execution events
  const executeChatCompletion = async (userPrompt: string) => {
    setIsLoading(true);
    setActiveTool(null);

    const conversationHistory = messages.map((m) => ({
      role: m.type === 'assistant' ? 'assistant' : 'user',
      content: m.text,
    }));
    conversationHistory.push({ role: 'user', content: userPrompt });

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: conversationHistory,
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      let assistantResponse = '';
      let currentEvent = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.replace('event: ', '').trim();
            } else if (line.startsWith('data: ')) {
              const dataStr = line.replace('data: ', '').trim();
              try {
                const data = JSON.parse(dataStr);

                if (currentEvent === 'tool_call') {
                  setActiveTool(`Executing ${data.tool}...`);
                } else if (currentEvent === 'tool_result') {
                  setActiveTool(null);
                  if (data.result?.action === 'client_navigate' && data.result?.url) {
                    window.open(data.result.url, '_blank', 'noopener,noreferrer');
                  }
                } else if (currentEvent === 'token') {
                  assistantResponse += data.text;
                } else if (currentEvent === 'error') {
                  throw new Error(data.error);
                }
              } catch (e: any) {
                if (currentEvent === 'error') throw e;
              }
            }
          }
        }
      }

      if (assistantResponse) {
        addMessage(assistantResponse, 'assistant');
        speakText(assistantResponse);
      }
    } catch (err: any) {
      addMessage(`Error: ${err.message || 'Failed to complete request.'}`, 'assistant');
    } finally {
      setIsLoading(false);
      setActiveTool(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;

    const prompt = inputText.trim();
    setInputText('');
    addMessage(prompt, 'user');
    await executeChatCompletion(prompt);
  };

  return (
    <div className="w-full bg-black/40 backdrop-blur-md rounded-lg border border-cyan-900 overflow-hidden shadow-2xl flex flex-col h-[520px]">
      {/* Console Header */}
      <div className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-950/80 via-purple-950/80 to-cyan-950/80 border-b border-cyan-900/60">
        <div className="flex items-center gap-2">
          <Terminal size={18} className="text-cyan-400" />
          <h3 className="text-cyan-200 font-semibold text-sm tracking-wide">Genius Local Command Console</h3>
        </div>
        <div className="flex items-center gap-2">
          {!isConnected ? (
            <div className="flex items-center gap-1.5 text-xs text-red-400 bg-red-950/50 px-2 py-0.5 rounded border border-red-800">
              <WifiOff size={13} />
              <span>Offline</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>FastAPI & Ollama Active</span>
            </div>
          )}
        </div>
      </div>

      {connectionError && (
        <div className="bg-red-950/40 border-b border-red-800/80 p-2.5 text-red-300 text-xs flex items-center gap-2">
          <AlertCircle size={14} className="text-red-400 shrink-0" />
          <span>{connectionError}</span>
        </div>
      )}

      {/* Message Stream Display */}
      <div ref={consoleRef} className="flex-1 p-4 overflow-y-auto space-y-3 font-mono text-xs">
        {messages.length === 0 && (
          <div className="text-center py-16 text-cyan-700/80">
            <p className="text-sm font-semibold text-cyan-400 mb-1">Genius AI Assistant Ready</p>
            <p className="text-xs">Ask in English or Hindi • Predict IPL matches • Manage tasks & reminders offline</p>
          </div>
        )}

        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-3 rounded-lg max-w-[85%] ${
              m.type === 'user'
                ? 'ml-auto bg-cyan-950/60 border border-cyan-800/60 text-cyan-100'
                : 'mr-auto bg-purple-950/50 border border-purple-900/50 text-purple-100'
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-cyan-500 mb-1">
              <span className="uppercase font-bold">{m.type === 'user' ? 'Operator' : 'Genius'}</span>
              <span>{new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div className="whitespace-pre-wrap leading-relaxed text-sm font-sans">{m.text}</div>
          </div>
        ))}

        {activeTool && (
          <div className="flex items-center gap-2 p-2 bg-yellow-950/40 border border-yellow-800/60 rounded text-yellow-300 text-xs animate-pulse">
            <Wrench size={14} className="animate-spin text-yellow-400" />
            <span>{activeTool}</span>
          </div>
        )}
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSubmit} className="p-3 bg-black/60 border-t border-cyan-900/60 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setIsListening(!isListening)}
          className={`p-2.5 rounded-lg border transition-all ${
            isListening
              ? 'bg-red-600 border-red-500 text-white animate-pulse'
              : 'bg-cyan-950/60 border-cyan-800/80 text-cyan-300 hover:bg-cyan-900/80'
          }`}
          title={isListening ? 'Stop Recording' : 'Start Voice Input'}
        >
          {isListening ? <MicOff size={18} /> : <Mic size={18} />}
        </button>

        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder={isListening ? 'Listening via browser microphone...' : 'Type a command or ask a question in Hindi / English...'}
          disabled={isLoading || isListening}
          className="flex-1 bg-black/50 border border-cyan-900/70 rounded-lg px-3.5 py-2 text-cyan-100 placeholder-cyan-700 text-sm focus:outline-none focus:border-cyan-500"
        />

        <button
          type="submit"
          disabled={isLoading || !inputText.trim()}
          className="bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-black font-bold p-2.5 rounded-lg flex items-center justify-center transition-all"
        >
          {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </form>
    </div>
  );
};

export default CommandConsole;