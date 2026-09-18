import React, { useState } from 'react';
import { Bot, Send, User, Sparkles, Clock } from 'lucide-react';
import { queryAgent } from '../api/client';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  latencyMs?: number;
  toolCalls?: Array<{ name: string; args: any; result?: any }>;
}

export const AgentChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'agent',
      text: "Hello! I am your Conversation Intelligence Agent. I can search across your meeting history, pull surrounding transcript context, track action items, or push meeting summaries to external tools.",
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: inputQuery.trim(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsLoading(true);

    try {
      const res = await queryAgent(userMsg.text);
      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.response || "No response generated.",
        latencyMs: res.latency_ms,
        toolCalls: res.tool_calls || [],
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        text: `Error invoking agent: ${err.message}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-xl shadow-xl backdrop-blur flex flex-col h-[650px]">
      {/* Chat Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-sky-500/10 text-sky-400 rounded-lg border border-sky-500/20">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white">ReAct Conversation Agent</h3>
            <p className="text-[11px] text-slate-400">Autonomous tool execution with Plan-and-Execute inner loop</p>
          </div>
        </div>
        <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2.5 py-0.5 rounded-full border border-emerald-500/30 flex items-center gap-1.5 font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Engine Online
        </span>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-[85%] ${msg.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
          >
            <div
              className={`w-7 h-7 rounded-lg shrink-0 flex items-center justify-center text-xs font-bold ${
                msg.sender === 'user'
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-800 text-sky-400 border border-slate-700'
              }`}
            >
              {msg.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            <div className="space-y-2">
              <div
                className={`p-3.5 rounded-xl text-sm leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-950 border border-slate-800/80 text-slate-200 shadow-sm'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.text}</p>
              </div>

              {msg.latencyMs !== undefined && (
                <div className="flex items-center gap-3 text-[10px] text-slate-500 font-mono px-1">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-slate-600" />
                    {msg.latencyMs}ms
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-3 mr-auto items-center text-xs text-slate-400 bg-slate-950 p-3 rounded-lg border border-slate-800">
            <Sparkles className="w-4 h-4 text-sky-400 animate-spin" />
            <span>Agent reasoning and evaluating tool calls...</span>
          </div>
        )}
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="p-3 border-t border-slate-800 bg-slate-950/60 flex gap-2">
        <input
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask anything: 'What did Alice agree to?', 'Find all discussions about pricing'..."
          disabled={isLoading}
          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
        />
        <button
          type="submit"
          disabled={isLoading || !inputQuery.trim()}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 text-white font-medium rounded-lg text-sm transition flex items-center gap-1.5"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
