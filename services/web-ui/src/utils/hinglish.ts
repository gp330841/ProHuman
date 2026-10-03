// Devanagari to Roman Hinglish transliterator with comprehensive English loanword mapping
const PHRASES: Record<string, string> = {
  'आई थिंक': 'I think',
  'लेट्स सी': "let's see",
  'थैंक यू': 'thank you',
  'थैंक यु': 'thank you',
  'गुड मॉर्निंग': 'good morning',
  'गुड आफ्टरनून': 'good afternoon',
  'गुड इवनिंग': 'good evening',
  'ऑल राइट': 'all right',
  'नो प्रॉब्लम': 'no problem',
  'बाय द वे': 'by the way',
};

const COMMON_REPLACEMENTS: Record<string, string> = {
  // Grammar & Pronouns
  'यह': 'yeh', 'वह': 'woh', 'है': 'hai', 'हैं': 'hain', 'था': 'tha', 'थी': 'thi', 'थे': 'the',
  'कि': 'ki', 'का': 'ka', 'के': 'ke', 'की': 'ki', 'को': 'ko', 'से': 'se', 'में': 'mein', 'पर': 'par',
  'और': 'aur', 'या': 'ya', 'नहीं': 'nahi', 'हाँ': 'haan', 'क्या': 'kya', 'क्यों': 'kyun', 'कैसे': 'kaise',
  'कब': 'kab', 'कहाँ': 'kahan', 'मुझे': 'mujhe', 'मुझको': 'mujhko', 'तुम्हें': 'tumhe', 'आप': 'aap',
  'हम': 'hum', 'वे': 'woh', 'काम': 'kaam', 'बात': 'baat', 'करना': 'karna', 'करते': 'karte', 'करता': 'karta',
  'करती': 'karti', 'किया': 'kiya', 'गया': 'gaya', 'गए': 'gaye', 'गई': 'gayi', 'सकते': 'sakte', 'सकता': 'sakta',
  'सकती': 'sakti', 'होना': 'hona', 'होता': 'hota', 'होते': 'hote', 'होती': 'hoti', 'रहा': 'raha',
  'रहे': 'rahe', 'रही': 'rahi', 'बहुत': 'bahut', 'ज्यादा': 'zyada', 'अच्छा': 'accha', 'ठीक': 'theek',
  'फैसला': 'faisla', 'दुकान': 'dukaan', 'देखना': 'dekhna', 'देखते': 'dekhte', 'देखा': 'dekha', 'देखो': 'dekho',
  'बाकी': 'baaki', 'रखना': 'rakhna', 'रखा': 'rakha', 'रखो': 'rakho', 'रखेंगे': 'rakhenge', 'फालतू': 'faltu',
  'कारखाना': 'karkhana', 'बोलो': 'bolo', 'बोलना': 'bolna', 'बोला': 'bola', 'बोल': 'bol',
  'सुना': 'suna', 'सुनो': 'suno', 'बताओ': 'batao', 'बताना': 'batana', 'समझा': 'samjha', 'समझो': 'samjho',
  'आया': 'aaya', 'जाओ': 'jao', 'आओ': 'aao', 'देंगे': 'denge', 'लेंगे': 'lenge',
  'होगा': 'hoga', 'होगी': 'hogi', 'होंगे': 'honge', 'चाहिए': 'chahiye', 'लेकिन': 'lekin', 'मगर': 'magar',
  'क्योंकि': 'kyunki', 'इसलिए': 'isliye', 'अगर': 'agar', 'तो': 'to', 'भी': 'bhi', 'ही': 'hi',
  'वाला': 'wala', 'वाली': 'wali', 'वाले': 'wale', 'लोग': 'log', 'सब': 'sab', 'सबको': 'sabko',

  // Tech, Software & English loanwords (Standard English spelling)
  'टाइपिंग': 'typing', 'टाइप': 'type', 'टाइटल': 'title', 'टाइटिल': 'title',
  'सजेस्ट': 'suggest', 'सजेशन': 'suggestion',
  'मॉडल': 'model', 'मॉडल्स': 'models', 'मोडल': 'model',
  'इम्प्लीमेंट': 'implement', 'इम्प्लीमेंटेशन': 'implementation',
  'ट्रांसक्रिप्शन': 'transcription', 'ट्रांसक्राइब': 'transcribe',
  'समराइजेशन': 'summarization', 'समरी': 'summary',
  'यूज': 'use', 'यूज़': 'use', 'यूज्ड': 'used',
  'हैलो': 'hello', 'हेलो': 'hello', 'हाय': 'hi',
  'टेस्ट': 'test', 'टेस्टिंग': 'testing', 'चेक': 'check', 'अपडेट': 'update', 'रिजल्ट': 'result',
  'स्क्रीन': 'screen', 'ऑनलाइन': 'online', 'लोकल': 'local', 'लोकली': 'locally',
  'ओके': 'okay', 'प्लीज': 'please', 'थैंक्स': 'thanks',
  'प्रोजेक्ट': 'project', 'सिस्टम': 'system', 'कोड': 'code', 'कोडिंग': 'coding',
  'फीचर': 'feature', 'फंक्शन': 'function', 'बटन': 'button', 'पेज': 'page', 'यूजर': 'user',
  'प्रॉब्लम': 'problem', 'इशू': 'issue', 'एरर': 'error', 'बग': 'bug', 'फिक्स': 'fix', 'सॉल्यूशन': 'solution',
  'चेंज': 'change', 'प्लान': 'plan', 'टाइम': 'time', 'कॉल': 'call', 'मैसेज': 'message', 'ईमेल': 'email',
  'नोट्स': 'notes', 'पॉइंट': 'point', 'पॉइंट्स': 'points', 'डिसीजन': 'decision', 'टास्क': 'task',
  'टीम': 'team', 'वर्क': 'work', 'स्टार्ट': 'start', 'स्टॉप': 'stop', 'नेक्स्ट': 'next',
  'बेस्ट': 'best', 'बेटर': 'better', 'लास्ट': 'last', 'फर्स्ट': 'first', 'क्लियर': 'clear',
  'डॉक्यूमेंट': 'document', 'फाइल': 'file', 'फोल्डर': 'folder', 'सर्वर': 'server', 'नेटवर्क': 'network',
  'इंटरनेट': 'internet', 'कंप्यूटर': 'computer', 'लैपटॉप': 'laptop', 'मोबाइल': 'mobile',
  'ऑडियो': 'audio', 'वीडियो': 'video', 'माइक': 'mic', 'स्पीकर': 'speaker', 'रिकॉर्डिंग': 'recording',
  'शेयर': 'share', 'सेंड': 'send', 'डाउनलोड': 'download', 'अपलोड': 'upload', 'इंस्टॉल': 'install',
  'लॉगिन': 'login', 'पासवर्ड': 'password', 'अकाउंट': 'account', 'सेटिंग': 'setting', 'सेटिंग्स': 'settings',
  'ऑप्शन': 'option', 'व्यू': 'view', 'एडिट': 'edit', 'डिलीट': 'delete', 'क्रिएट': 'create',
  'जनरेट': 'generate', 'रीजनरेट': 'regenerate', 'ट्रांसलेट': 'translate', 'ट्रांसलेशन': 'translation',
  'इंग्लिश': 'English', 'हिंदी': 'Hindi', 'हिंग्लिश': 'Hinglish', 'लैंग्वेज': 'language', 'वॉयस': 'voice',
  'स्पीच': 'speech', 'टेक्स्ट': 'text', 'चैट': 'chat', 'बॉट': 'bot', 'एजेंट': 'agent', 'रन': 'run',
  'फास्ट': 'fast', 'स्लो': 'slow', 'रेडी': 'ready', 'डन': 'done', 'वेट': 'wait', 'हेल्प': 'help',
  'सपोर्ट': 'support', 'मीटिंग': 'meeting', 'स्टोर': 'store', 'डाटा': 'data', 'डेटा': 'data', 'रिकॉर्ड': 'record'
};

const VOWELS: Record<string, string> = {
  '\u0905': 'a', '\u0906': 'aa', '\u0907': 'i', '\u0908': 'i', '\u0909': 'u', '\u090a': 'u',
  '\u090b': 'ri', '\u090e': 'e', '\u090f': 'e', '\u0910': 'ai', '\u0911': 'o', '\u0912': 'o',
  '\u0913': 'o', '\u0914': 'au'
};

const MATRAS: Record<string, string> = {
  '\u093e': 'a', '\u093f': 'i', '\u0940': 'i', '\u0941': 'u', '\u0942': 'u', '\u0943': 'ri',
  '\u0947': 'e', '\u0948': 'ai', '\u0949': 'o', '\u094a': 'o', '\u094b': 'o', '\u094c': 'au',
  '\u094d': ''
};

const CONSONANTS: Record<string, string> = {
  '\u0915': 'k', '\u0916': 'kh', '\u0917': 'g', '\u0918': 'gh', '\u0919': 'ng',
  '\u091a': 'ch', '\u091b': 'chh', '\u091c': 'j', '\u091d': 'jh', '\u091e': 'ny',
  '\u091f': 't', '\u0920': 'th', '\u0921': 'd', '\u0922': 'dh', '\u0923': 'n',
  '\u0924': 't', '\u0925': 'th', '\u0926': 'd', '\u0927': 'dh', '\u0928': 'n',
  '\u092a': 'p', '\u092b': 'f', '\u092c': 'b', '\u092d': 'bh', '\u092e': 'm',
  '\u092f': 'y', '\u0930': 'r', '\u0932': 'l', '\u0935': 'v', '\u0936': 'sh',
  '\u0937': 'sh', '\u0938': 's', '\u0939': 'h',
  '\u0958': 'q', '\u0959': 'kh', '\u095a': 'g', '\u095b': 'z', '\u095c': 'r', '\u095d': 'rh', '\u095e': 'f'
};

export function devanagariToHinglish(text: string): string {
  if (!text) return '';

  let processed = text;
  for (const [phrase, replacement] of Object.entries(PHRASES)) {
    processed = processed.split(phrase).join(replacement);
  }

  const words = processed.split(' ');
  const outWords: string[] = [];

  for (const word of words) {
    const cleaned = word.replace(/^[.,!?;:'"।॥]+|[.,!?;:'"।॥]+$/g, '');
    const prefix = word.match(/^[.,!?;:'"।॥]+/)?.[0] || '';
    const suffix = word.match(/[.,!?;:'"।॥]+$/)?.[0] || '';

    if (COMMON_REPLACEMENTS[cleaned]) {
      outWords.push(prefix + COMMON_REPLACEMENTS[cleaned] + suffix);
      continue;
    }

    if (!/[\u0900-\u097F]/.test(word)) {
      outWords.push(word);
      continue;
    }

    const res: string[] = [];
    const n = word.length;
    let i = 0;

    while (i < n) {
      const c = word[i];
      if (VOWELS[c]) {
        res.push(VOWELS[c]);
      } else if (CONSONANTS[c]) {
        const base = CONSONANTS[c];
        if (i + 1 < n && MATRAS[word[i + 1]] !== undefined) {
          res.push(base + MATRAS[word[i + 1]]);
          i += 1;
        } else if (i + 1 < n && word[i + 1] === '\u094d') {
          res.push(base);
          i += 1;
        } else {
          if (i + 1 === n || !/[\u0900-\u097F]/.test(word[i + 1])) {
            res.push(base);
          } else if (i + 1 < n && CONSONANTS[word[i + 1]]) {
            res.push(base + 'a');
          } else {
            res.push(base);
          }
        }
      } else if (c === '\u0902' || c === '\u0901') {
        res.push('n');
      } else if (c === '\u0964' || c === '\u0965') {
        res.push('.');
      } else {
        res.push(c);
      }
      i += 1;
    }
    outWords.push(res.join(''));
  }

  return outWords.join(' ');
}
