// Devanagari to Roman Hinglish transliterator
const COMMON_REPLACEMENTS: Record<string, string> = {
  'यह': 'yeh',
  'वह': 'woh',
  'है': 'hai',
  'हैं': 'hain',
  'था': 'tha',
  'थी': 'thi',
  'थे': 'the',
  'कि': 'ki',
  'का': 'ka',
  'के': 'ke',
  'की': 'ki',
  'को': 'ko',
  'से': 'se',
  'में': 'mein',
  'पर': 'par',
  'और': 'aur',
  'या': 'ya',
  'नहीं': 'nahi',
  'हाँ': 'haan',
  'क्या': 'kya',
  'क्यों': 'kyun',
  'कैसे': 'kaise',
  'कब': 'kab',
  'कहाँ': 'kahan',
  'मुझे': 'mujhe',
  'मुझको': 'mujhko',
  'तुम्हें': 'tumhe',
  'आप': 'aap',
  'हम': 'hum',
  'वे': 'woh',
  'काम': 'kaam',
  'बात': 'baat',
  'करना': 'karna',
  'करते': 'karte',
  'करता': 'karta',
  'करती': 'karti',
  'किया': 'kiya',
  'गया': 'gaya',
  'गए': 'gaye',
  'गई': 'gayi',
  'सकते': 'sakte',
  'सकता': 'sakta',
  'सकती': 'sakti',
  'होना': 'hona',
  'होता': 'hota',
  'होते': 'hote',
  'होती': 'hoti',
  'रहा': 'raha',
  'रहे': 'rahe',
  'रही': 'rahi',
  'बहुत': 'bahut',
  'ज्यादा': 'zyada',
  'अच्छा': 'accha',
  'ठीक': 'theek',
  'मीटिंग': 'meeting',
  'स्टोर': 'store',
  'डाटा': 'data',
  'रिकॉर्ड': 'record',
  'समरी': 'summary',
  'टाइम': 'time',
  'प्रोजेक्ट': 'project',
  'फैसला': 'faisla',
  'दुकान': 'dukaan',
  'देखना': 'dekhna',
  'बाकी': 'baaki',
};

const VOWELS: Record<string, string> = {
  '\u0905': 'a', '\u0906': 'aa', '\u0907': 'i', '\u0908': 'ee', '\u0909': 'u', '\u090a': 'oo',
  '\u090b': 'ri', '\u090e': 'e', '\u090f': 'e', '\u0910': 'ai', '\u0911': 'o', '\u0912': 'o',
  '\u0913': 'o', '\u0914': 'au'
};

const MATRAS: Record<string, string> = {
  '\u093e': 'a', '\u093f': 'i', '\u0940': 'i', '\u0941': 'u', '\u0942': 'oo', '\u0943': 'ri',
  '\u0947': 'e', '\u0948': 'ai', '\u0949': 'o', '\u094a': 'o', '\u094b': 'o', '\u094c': 'au',
  '\u094d': ''
};

const CONSONANTS: Record<string, string> = {
  '\u0915': 'k', '\u0916': 'kh', '\u0917': 'g', '\u0918': 'gh', '\u0919': 'ng',
  '\u091a': 'ch', '\u091b': 'chh', '\u091c': 'j', '\u091d': 'jh', '\u091e': 'ny',
  '\u091f': 't', '\u0920': 'th', '\u0921': 'd', '\u0922': 'dh', '\u0923': 'n',
  '\u0924': 't', '\u0925': 'th', '\u0926': 'd', '\u0927': 'dh', '\u0928': 'n',
  '\u092a': 'p', '\u092b': 'ph', '\u092c': 'b', '\u092d': 'bh', '\u092e': 'm',
  '\u092f': 'y', '\u0930': 'r', '\u0932': 'l', '\u0935': 'v', '\u0936': 'sh',
  '\u0937': 'sh', '\u0938': 's', '\u0939': 'h',
  '\u0958': 'q', '\u0959': 'kh', '\u095a': 'g', '\u095b': 'z', '\u095c': 'r', '\u095d': 'rh', '\u095e': 'f'
};

export function devanagariToHinglish(text: string): string {
  if (!text) return '';
  const words = text.split(' ');
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
