import React, { useState, useRef, useEffect } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  Copy, 
  Check, 
  Trash2, 
  Zap 
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
];

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

    try {
      const res = await queryAgent(userMsg.text, activeUser.id);
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.response || "No response generated.",
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
      let formatted = line;
      if (line.startsWith('**') && line.endsWith('**')) {
        return (
          <h4 key={idx} className="font-bold text-sky-600 dark:text-sky-300 text-sm my-1">
            {line.replace(/\*\*/g, '')}
          </h4>
        );
      }
      if (line.startsWith('- ') || line.startsWith('• ')) {
        const itemText = line.substring(2);
        return (
          <li key={idx} className="ml-4 list-disc text-slate-700 dark:text-slate-300 text-xs md:text-sm my-0.5">
            {renderBoldSpans(itemText)}
          </li>
        );
      }
      return (
        <p key={idx} className={`${line.trim() === '' ? 'h-2' : 'my-1'}`}>
          {renderBoldSpans(formatted)}
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

  return (
    <div className="glass-card rounded-3xl flex flex-col h-[700px] relative overflow-hidden">
      {/* Header */}
      <div className="p-4 md:p-5 border-b border-slate-200 dark:border-white/[0.08] flex items-center justify-between bg-slate-50/50 dark:bg-white/[0.02]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-sky-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/25">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight">ProHuman ReAct Intelligence</h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-50 dark:bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-200 dark:border-sky-500/30">
                ✦ Gemini 3.5
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Contextual search, historical memory, and automated execution</p>
          </div>
        </div>

        <button
          onClick={handleClear}
          className="text-xs text-slate-500 dark:text-slate-400 hover:text-rose-500 dark:hover:text-rose-400 transition flex items-center gap-1.5 px-3 py-1.5 rounded-xl glass-pill cursor-pointer"
          title="Clear conversation"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Clear Chat</span>
        </button>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-5">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-[88%] md:max-w-[80%] ${
              msg.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
            }`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-xl shrink-0 flex items-center justify-center text-xs font-bold shadow-sm ${
                msg.sender === 'user'
                  ? 'bg-gradient-to-tr from-sky-500 to-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.1] text-sky-600 dark:text-sky-400'
              }`}
            >
              {msg.sender === 'user' ? activeUser.name.charAt(0) : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble */}
            <div className="space-y-1.5">
              <div
                className={`p-4 rounded-2xl text-xs md:text-sm leading-relaxed shadow-sm transition-all ${
                  msg.sender === 'user'
                    ? 'bg-gradient-to-r from-sky-500 to-indigo-600 text-white rounded-tr-sm shadow-md shadow-sky-500/15'
                    : 'bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] text-slate-800 dark:text-slate-200 rounded-tl-sm backdrop-blur-md shadow-sm'
                }`}
              >
                {renderFormattedText(msg.text)}
              </div>

              {/* Message Footer */}
              <div
                className={`flex items-center gap-3 text-[10px] text-slate-400 dark:text-slate-500 px-1 ${
                  msg.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <span>{msg.timestamp}</span>
                {msg.latencyMs !== undefined && (
                  <span className="flex items-center gap-1 text-slate-500 font-mono">
                    <Zap className="w-3 h-3 text-amber-500 dark:text-amber-400" />
                    {(msg.latencyMs / 1000).toFixed(1)}s
                  </span>
                )}
                {msg.sender === 'agent' && (
                  <button
                    onClick={() => handleCopy(msg.id, msg.text)}
                    className="hover:text-slate-700 dark:hover:text-slate-300 transition flex items-center gap-1 cursor-pointer"
                  >
                    {copiedId === msg.id ? (
                      <Check className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                    <span>{copiedId === msg.id ? 'Copied' : 'Copy'}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 max-w-[80%] mr-auto">
            <div className="w-8 h-8 rounded-xl bg-slate-100 dark:bg-white/[0.06] border border-slate-200 dark:border-white/[0.1] shrink-0 flex items-center justify-center text-sky-500 dark:text-sky-400">
              <Bot className="w-4 h-4 animate-bounce" />
            </div>
            <div className="p-4 rounded-2xl bg-white dark:bg-white/[0.03] border border-slate-200 dark:border-white/[0.08] text-slate-600 dark:text-slate-400 text-xs flex items-center gap-2 shadow-sm">
              <Sparkles className="w-4 h-4 text-sky-500 dark:text-sky-400 animate-spin" />
              <span>Thinking with Gemini & searching conversation history...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion Starter Pills */}
      <div className="px-4 py-2 border-t border-slate-200 dark:border-white/[0.05] bg-slate-50/70 dark:bg-white/[0.01] flex items-center gap-2 overflow-x-auto no-scrollbar">
        <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500 shrink-0 flex items-center gap-1">
          Suggestions:
        </span>
        {STARTER_PROMPTS.map((prompt, i) => (
          <button
            key={i}
            onClick={() => handleSend(prompt.query)}
            disabled={isLoading}
            className="text-xs text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white glass-pill px-3 py-1 rounded-full whitespace-nowrap transition cursor-pointer hover:border-sky-400 shrink-0 flex items-center gap-1.5"
          >
            <span>{prompt.icon}</span>
            <span>{prompt.label}</span>
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div className="p-4 border-t border-slate-200 dark:border-white/[0.08] bg-white/90 dark:bg-slate-950/70 backdrop-blur-xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2 relative"
        >
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={isLoading}
            placeholder="Ask anything in Hinglish or English (e.g. 'What did we decide about the timeline?')..."
            className="flex-1 bg-slate-50 dark:bg-white/[0.04] border border-slate-300 dark:border-white/[0.1] rounded-2xl pl-4 pr-12 py-3 text-xs md:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500/50 transition"
          />
          <button
            type="submit"
            disabled={!inputQuery.trim() || isLoading}
            className="absolute right-2 top-2 p-2 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:hover:scale-100 text-white transition shadow-md shadow-sky-500/20 cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
