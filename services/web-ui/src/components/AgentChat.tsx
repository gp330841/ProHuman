import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  Send,
  Sparkles,
  Copy,
  Check,
  Trash2,
  Zap,
  MessageSquare,
} from 'lucide-react';
import { queryAgent } from '../api/client';
import { useUser } from '../context/UserContext';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  latencyMs?: number;
  timestamp: string;
}

const STARTER_PROMPTS = [
  { icon: '⚡', label: 'Summary', query: 'Latest meeting ka summary Hinglish me batao' },
  { icon: '🎯', label: 'Action Items', query: 'Mere pending action items aur tasks kya hain?' },
  { icon: '💡', label: 'Decisions', query: 'Recent meetings me kya decisions finalize hue the?' },
  { icon: '💰', label: 'Budget', query: 'Budget aur timeline ke baare me kya discuss hua tha?' },
  { icon: '👥', label: 'Attendees', query: 'Last meeting me kaun kaun tha?' },
];

const TypingDots = () => (
  <div className="flex items-center gap-1.5 py-1 px-1">
    <span className="w-2 h-2 rounded-full bg-sky-400 dark:bg-sky-500 typing-dot" />
    <span className="w-2 h-2 rounded-full bg-indigo-400 dark:bg-indigo-500 typing-dot" />
    <span className="w-2 h-2 rounded-full bg-violet-400 dark:bg-violet-500 typing-dot" />
  </div>
);

export const AgentChat: React.FC = () => {
  const { activeUser } = useUser();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: `Namaste ${activeUser.name}! Main ProHuman ka ReAct Conversation Intelligence Agent hoon. Aap mujhse kisi bhi meeting ke decisions, action items ya summary ke baare me fluent Roman Hinglish me pooch sakte hain.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText || inputQuery).trim();
    if (!textToSend || isLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsLoading(true);
    setTimeout(() => inputRef.current?.focus(), 50);

    try {
      const res = await queryAgent(userMsg.text, activeUser.id);
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.response || 'No response generated.',
        latencyMs: res.latency_ms,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        text: `Error connecting to agent: ${err.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleClear = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        sender: 'agent',
        text: `Chat reset kiya gaya. Main aapki kya sahayata kar sakta hoon, ${activeUser.name}?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const renderFormattedText = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ') || (line.startsWith('**') && line.endsWith('**') && line.length > 4)) {
        return (
          <h4 key={idx} className="font-bold text-slate-900 dark:text-white text-sm my-2 first:mt-0">
            {line.replace(/^###\s*/, '').replace(/\*\*/g, '')}
          </h4>
        );
      }
      if (line.startsWith('- ') || line.startsWith('• ') || line.match(/^\d+\.\s/)) {
        const itemText = line.replace(/^[-•]\s/, '').replace(/^\d+\.\s/, '');
        return (
          <li key={idx} className="ml-4 text-slate-700 dark:text-slate-300 text-xs md:text-sm my-0.5 leading-relaxed">
            {renderBoldSpans(itemText)}
          </li>
        );
      }
      return (
        <p key={idx} className={`text-xs md:text-sm leading-relaxed ${line.trim() === '' ? 'h-2' : 'my-0.5'}`}>
          {renderBoldSpans(line)}
        </p>
      );
    });
  };

  const renderBoldSpans = (str: string) => {
    const parts = str.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-slate-900 dark:text-white">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  const isEmpty = messages.length === 1 && messages[0].id === 'welcome';

  return (
    <div className="glass-card rounded-3xl flex flex-col h-[calc(100vh-180px)] min-h-[560px] max-h-[800px] relative overflow-hidden">

      {/* ── Header ── */}
      <div className="px-5 py-4 border-b border-slate-200 dark:border-white/[0.07] flex items-center justify-between bg-white/60 dark:bg-white/[0.015] shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
            <Bot className="w-4.5 h-4.5 text-white" strokeWidth={2} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">ProHuman ReAct Agent</h3>
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-violet-50 dark:bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-200 dark:border-violet-500/25">
                ✦ Live
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Contextual memory & Hinglish intelligence</p>
          </div>
        </div>
        <button
          onClick={handleClear}
          className="text-xs text-slate-400 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-pill cursor-pointer"
          title="Clear conversation"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Clear</span>
        </button>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-5 space-y-4">
        {isEmpty && (
          <div className="text-center py-8 animate-fade-in">
            <div className="w-14 h-14 rounded-3xl bg-gradient-to-br from-violet-500/20 to-indigo-600/20 border border-violet-200 dark:border-violet-500/25 flex items-center justify-center mx-auto mb-3">
              <MessageSquare className="w-7 h-7 text-violet-500 dark:text-violet-400" />
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">Ask me anything</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">About your meetings, decisions, or action items</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={msg.id}
            className={`flex gap-2.5 animate-fade-in-up ${msg.sender === 'user' ? 'flex-row-reverse ml-auto max-w-[85%]' : 'mr-auto max-w-[90%] md:max-w-[80%]'}`}
            style={{ animationDelay: `${i * 0.03}s` }}
          >
            {/* Avatar */}
            <div className={`w-7 h-7 rounded-xl shrink-0 flex items-center justify-center text-[10px] font-bold shadow-sm mt-0.5 ${
              msg.sender === 'user'
                ? `bg-gradient-to-tr ${activeUser.gradient} text-white`
                : 'bg-slate-100 dark:bg-white/[0.07] border border-slate-200 dark:border-white/[0.1] text-violet-600 dark:text-violet-400'
            }`}>
              {msg.sender === 'user' ? activeUser.name.charAt(0) : <Bot className="w-3.5 h-3.5" />}
            </div>

            {/* Bubble */}
            <div className="space-y-1.5 min-w-0">
              <div className={`px-4 py-3 rounded-2xl text-xs md:text-sm leading-relaxed shadow-sm ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-r from-sky-500 to-indigo-600 text-white rounded-tr-sm shadow-sky-500/15'
                  : 'bg-white dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] text-slate-800 dark:text-slate-200 rounded-tl-sm'
              }`}>
                {renderFormattedText(msg.text)}
              </div>

              {/* Footer */}
              <div className={`flex items-center gap-3 text-[10px] text-slate-400 dark:text-slate-500 px-1 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <span className="font-mono">{msg.timestamp}</span>
                {msg.latencyMs !== undefined && (
                  <span className="flex items-center gap-1 font-mono">
                    <Zap className="w-3 h-3 text-amber-400" />
                    {(msg.latencyMs / 1000).toFixed(1)}s
                  </span>
                )}
                {msg.sender === 'agent' && (
                  <button
                    onClick={() => handleCopy(msg.id, msg.text)}
                    className="flex items-center gap-1 hover:text-slate-700 dark:hover:text-slate-300 transition cursor-pointer"
                  >
                    {copiedId === msg.id
                      ? <><Check className="w-3 h-3 text-emerald-500" /><span>Copied</span></>
                      : <><Copy className="w-3 h-3" /><span>Copy</span></>
                    }
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex gap-2.5 mr-auto animate-fade-in">
            <div className="w-7 h-7 rounded-xl bg-slate-100 dark:bg-white/[0.07] border border-slate-200 dark:border-white/[0.1] shrink-0 flex items-center justify-center mt-0.5">
              <Sparkles className="w-3.5 h-3.5 text-violet-500 dark:text-violet-400 animate-spin" />
            </div>
            <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.08] shadow-sm">
              <TypingDots />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Starter Chips ── */}
      <div className="px-4 py-2 border-t border-slate-200 dark:border-white/[0.05] bg-slate-50/80 dark:bg-white/[0.01] flex items-center gap-2 overflow-x-auto no-scrollbar shrink-0">
        <span className="text-[9px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 shrink-0">Quick:</span>
        {STARTER_PROMPTS.map((prompt, i) => (
          <button
            key={i}
            onClick={() => handleSend(prompt.query)}
            disabled={isLoading}
            className="text-[11px] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white glass-pill px-3 py-1.5 rounded-full whitespace-nowrap transition cursor-pointer hover:border-violet-400/50 shrink-0 flex items-center gap-1.5 disabled:opacity-40"
          >
            <span>{prompt.icon}</span>
            <span>{prompt.label}</span>
          </button>
        ))}
      </div>

      {/* ── Input ── */}
      <div className="p-4 border-t border-slate-200 dark:border-white/[0.07] bg-white/90 dark:bg-[#060a12]/80 backdrop-blur-xl shrink-0">
        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(); }}
          className="flex items-center gap-2.5 relative"
        >
          <input
            ref={inputRef}
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isLoading}
            placeholder="Kuch bhi poochho — Hinglish ya English mein..."
            className="flex-1 bg-slate-50 dark:bg-white/[0.04] border border-slate-200 dark:border-white/[0.09] rounded-2xl pl-4 pr-12 py-3 text-xs md:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-violet-400 dark:focus:border-violet-500 focus:ring-1 focus:ring-violet-400/30 dark:focus:ring-violet-500/30 transition"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isLoading}
            className="absolute right-1.5 top-1.5 p-2.5 rounded-xl bg-gradient-to-tr from-violet-500 to-indigo-600 hover:from-violet-400 hover:to-indigo-500 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 text-white transition shadow-md shadow-violet-500/20 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
};
