import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Paperclip, 
  X, 
  FileText, 
  Bot, 
  User, 
  RotateCw, 
  AlertCircle, 
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { uploadChatAttachment, ExtractedFileResult } from '../../services/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  attachmentName?: string;
  timestamp: string;
}

const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.csv', '.json', '.pdf'];
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

const ChatPanel: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hello! I am Genius AI Assistant. You can chat with me, ask questions, or attach text files, documents (.pdf, .txt, .md), and data files (.csv, .json) for analysis.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Attachment state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeTool]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorBanner(null);
    if (!e.target.files || e.target.files.length === 0) return;

    const file = e.target.files[0];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setErrorBanner(`Unsupported file type '${ext}'. Please select a .txt, .md, .csv, .json, or .pdf file.`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    if (file.size === 0) {
      setErrorBanner(`File '${file.name}' is empty (0 bytes).`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setErrorBanner(`File '${file.name}' exceeds the 5MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB).`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setSelectedFile(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachment = () => {
    setSelectedFile(null);
    setErrorBanner(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!inputText.trim() && !selectedFile) || isLoading || isExtracting) return;

    setErrorBanner(null);
    const userPrompt = inputText.trim();
    let finalPrompt = userPrompt;
    let attachmentDisplayName: string | undefined = undefined;

    // 1. Handle file upload and text extraction if attachment is present
    if (selectedFile) {
      setIsExtracting(true);
      try {
        const extracted: ExtractedFileResult = await uploadChatAttachment(selectedFile);
        attachmentDisplayName = selectedFile.name;
        
        const fileHeader = `[Attached File: ${extracted.filename} (${extracted.file_type}, ${formatFileSize(extracted.size_bytes)})]\n` +
          `--- BEGIN EXTRACTED CONTENT ---\n` +
          `${extracted.text_content}\n` +
          `--- END EXTRACTED CONTENT ---`;

        finalPrompt = userPrompt
          ? `${fileHeader}\n\nUser Question: ${userPrompt}`
          : `${fileHeader}\n\nPlease summarize the contents of this attached file and highlight its key points.`;
      } catch (err: unknown) {
        setIsExtracting(false);
        setErrorBanner(err instanceof Error ? err.message : 'Failed to extract text from attachment.');
        return;
      } finally {
        setIsExtracting(false);
      }
    }

    // Add user message to conversation
    const userMessageId = `user-${Date.now()}`;
    const newMessages: Message[] = [
      ...messages,
      {
        id: userMessageId,
        role: 'user',
        content: userPrompt || `[Attached: ${selectedFile?.name}] Please analyze this document.`,
        attachmentName: attachmentDisplayName,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ];

    setMessages(newMessages);
    setInputText('');
    setSelectedFile(null);
    setIsLoading(true);
    setActiveTool(null);

    // Prepare payload for backend streaming agent
    const historyPayload = newMessages.map((m) => ({
      role: m.role,
      content: m.content
    }));
    // Ensure the last message contains the extracted file payload
    historyPayload[historyPayload.length - 1].content = finalPrompt;

    // Create placeholder assistant message for token streaming
    const assistantMessageId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: historyPayload,
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
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
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? { ...msg, content: msg.content + data.text }
                        : msg
                    )
                  );
                } else if (currentEvent === 'error') {
                  throw new Error(data.error);
                }
              } catch (e: unknown) {
                if (currentEvent === 'error') throw e;
              }
            }
          }
        }
      }
    } catch (err: unknown) {
      const errText = err instanceof Error ? err.message : 'Failed to complete assistant request.';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: msg.content ? `${msg.content}\n\n[Error: ${errText}]` : `Error: ${errText}` }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
      setActiveTool(null);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-950/60 rounded-xl border border-cyan-900/40 backdrop-blur-md shadow-2xl overflow-hidden">
      {/* Top Chat Header */}
      <div className="px-5 py-3.5 border-b border-cyan-900/40 bg-gray-900/40 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center shadow-md shadow-cyan-500/20">
            <Bot size={18} className="text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-sm font-bold text-gray-100 tracking-wide">Genius Assistant</h2>
              <span className="flex items-center text-[10px] px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                <Sparkles size={10} className="mr-1 text-cyan-400" />
                Live Agent
              </span>
            </div>
            <p className="text-[11px] text-gray-400">Contextual chat with document and data analysis</p>
          </div>
        </div>

        <div className="text-[11px] text-gray-400 font-mono hidden sm:block">
          Accepts .txt, .md, .csv, .json, .pdf (Max 5MB)
        </div>
      </div>

      {/* Error Banner */}
      {errorBanner && (
        <div className="mx-4 mt-3 px-3.5 py-2 rounded-lg bg-amber-950/60 border border-amber-800/60 text-amber-300 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle size={15} className="text-amber-400 shrink-0" />
            <span>{errorBanner}</span>
          </div>
          <button 
            onClick={() => setErrorBanner(null)} 
            className="text-amber-400 hover:text-amber-200 ml-2"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex items-start gap-3 ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-purple-900/60 border border-purple-500/40 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                <Bot size={15} className="text-purple-300" />
              </div>
            )}

            <div
              className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-md ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-blue-900/60 to-cyan-900/60 border border-cyan-700/50 text-cyan-100'
                  : 'bg-gradient-to-r from-purple-950/70 to-indigo-950/70 border border-purple-800/40 text-gray-200'
              }`}
            >
              {/* Attachment chip in user message */}
              {msg.attachmentName && (
                <div className="mb-2 pb-1.5 border-b border-cyan-800/40 flex items-center space-x-1.5 text-xs text-cyan-300">
                  <FileText size={13} className="text-cyan-400" />
                  <span className="font-medium truncate max-w-[200px]">{msg.attachmentName}</span>
                </div>
              )}

              {/* Message text content */}
              <div className="whitespace-pre-wrap leading-relaxed break-words">
                {msg.content || (
                  <span className="inline-flex items-center text-xs text-purple-300">
                    <RotateCw size={12} className="animate-spin mr-1.5 text-purple-400" />
                    Thinking...
                  </span>
                )}
              </div>

              <div
                className={`mt-1.5 text-[10px] ${
                  msg.role === 'user' ? 'text-cyan-400/60 text-right' : 'text-gray-400/60'
                }`}
              >
                {msg.timestamp}
              </div>
            </div>

            {msg.role === 'user' && (
              <div className="w-7 h-7 rounded-full bg-cyan-900/60 border border-cyan-500/40 flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                <User size={15} className="text-cyan-300" />
              </div>
            )}
          </div>
        ))}

        {/* Active Tool execution banner */}
        {activeTool && (
          <div className="flex items-center space-x-2 text-xs text-cyan-400 bg-cyan-950/40 border border-cyan-800/40 rounded-lg px-3 py-2 w-fit">
            <RotateCw size={13} className="animate-spin text-cyan-400" />
            <span className="font-mono">{activeTool}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input and Attachment Footer */}
      <div className="p-3 border-t border-cyan-900/40 bg-gray-900/60">
        {/* Selected file attachment badge */}
        {selectedFile && (
          <div className="mb-2 flex items-center justify-between px-3 py-1.5 rounded-lg bg-cyan-950/50 border border-cyan-700/60 text-xs text-cyan-200">
            <div className="flex items-center space-x-2 truncate">
              <FileText size={15} className="text-cyan-400 shrink-0" />
              <span className="font-medium truncate max-w-[240px]">{selectedFile.name}</span>
              <span className="text-[10px] text-gray-400 shrink-0">
                ({formatFileSize(selectedFile.size)})
              </span>
              <span className="flex items-center text-[10px] text-emerald-400 shrink-0">
                <CheckCircle2 size={11} className="mr-0.5" /> Ready
              </span>
            </div>
            <button
              onClick={removeAttachment}
              className="p-1 text-gray-400 hover:text-cyan-300 rounded hover:bg-cyan-900/30 transition-colors"
              title="Remove attachment"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="flex items-center space-x-2">
          {/* Hidden file input */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".txt,.md,.csv,.json,.pdf"
            className="hidden"
          />

          {/* Attachment trigger button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || isExtracting}
            className={`p-2.5 rounded-lg border transition-all ${
              selectedFile 
                ? 'bg-cyan-900/60 border-cyan-500 text-cyan-300' 
                : 'bg-gray-800/70 border-cyan-900/40 text-gray-400 hover:text-cyan-400 hover:border-cyan-700/50'
            } disabled:opacity-50`}
            title="Attach file (.txt, .md, .csv, .json, .pdf)"
          >
            <Paperclip size={18} />
          </button>

          {/* Prompt text input */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={
              selectedFile
                ? `Ask a question about ${selectedFile.name} (or leave blank to summarize)...`
                : 'Ask Genius Assistant anything...'
            }
            disabled={isLoading || isExtracting}
            className="flex-1 bg-gray-950/80 border border-cyan-900/50 rounded-lg px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500/70 focus:ring-1 focus:ring-cyan-500/50 transition-all disabled:opacity-50"
          />

          {/* Send button */}
          <button
            type="submit"
            disabled={(!inputText.trim() && !selectedFile) || isLoading || isExtracting}
            className="p-2.5 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white shadow-md shadow-purple-600/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send Message"
          >
            {isExtracting ? (
              <RotateCw size={18} className="animate-spin text-white" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatPanel;
