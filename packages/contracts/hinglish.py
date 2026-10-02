"""
Devanagari to Hinglish transliteration utilities.

Provides functions and mappings to convert Hindi text written in Devanagari
script into Roman script (Hinglish).
"""
from __future__ import annotations

COMMON_REPLACEMENTS = {
    "यह": "yeh", "वह": "woh", "है": "hai", "हैं": "hain", "था": "tha", "थी": "thi", "थे": "the",
    "कि": "ki", "का": "ka", "के": "ke", "की": "ki", "को": "ko", "से": "se", "में": "mein", "पर": "par",
    "और": "aur", "या": "ya", "नहीं": "nahi", "हाँ": "haan", "क्या": "kya", "क्यों": "kyun", "कैसे": "kaise",
    "कब": "kab", "कहाँ": "kahan", "मुझे": "mujhe", "मुझको": "mujhko", "तुम्हें": "tumhe", "आप": "aap",
    "हम": "hum", "वे": "woh", "काम": "kaam", "बात": "baat", "करना": "karna", "करते": "karte", "करता": "karta",
    "करती": "karti", "किया": "kiya", "गया": "gaya", "गए": "gaye", "गई": "gayi", "सकते": "sakte", "सकता": "sakta",
    "सकती": "sakti", "होना": "hona", "होता": "hota", "होते": "hote", "होती": "hoti", "रहा": "raha",
    "रहे": "rahe", "रही": "rahi", "बहुत": "bahut", "ज्यादा": "zyada", "अच्छा": "accha", "ठीक": "theek",
    "मीटिंग": "meeting", "स्टोर": "store", "डाटा": "data", "रिकॉर्ड": "record", "समरी": "summary",
    "टाइम": "time", "प्रोजेक्ट": "project", "फैसला": "faisla", "दुकान": "dukaan", "देखना": "dekhna", "बाकी": "baaki"
}

VOWELS = {
    "\u0905": "a", "\u0906": "aa", "\u0907": "i", "\u0908": "ee", "\u0909": "u", "\u090a": "oo",
    "\u090b": "ri", "\u090e": "e", "\u090f": "e", "\u0910": "ai", "\u0911": "o", "\u0912": "o",
    "\u0913": "o", "\u0914": "au"
}

MATRAS = {
    "\u093e": "a", "\u093f": "i", "\u0940": "i", "\u0941": "u", "\u0942": "oo", "\u0943": "ri",
    "\u0947": "e", "\u0948": "ai", "\u0949": "o", "\u094a": "o", "\u094b": "o", "\u094c": "au",
    "\u094d": ""
}

CONSONANTS = {
    "\u0915": "k", "\u0916": "kh", "\u0917": "g", "\u0918": "gh", "\u0919": "ng",
    "\u091a": "ch", "\u091b": "chh", "\u091c": "j", "\u091d": "jh", "\u091e": "ny",
    "\u091f": "t", "\u0920": "th", "\u0921": "d", "\u0922": "dh", "\u0923": "n",
    "\u0924": "t", "\u0925": "th", "\u0926": "d", "\u0927": "dh", "\u0928": "n",
    "\u092a": "p", "\u092b": "ph", "\u092c": "b", "\u092d": "bh", "\u092e": "m",
    "\u092f": "y", "\u0930": "r", "\u0932": "l", "\u0935": "v", "\u0936": "sh",
    "\u0937": "sh", "\u0938": "s", "\u0939": "h",
    "\u0958": "q", "\u0959": "kh", "\u095a": "g", "\u095b": "z", "\u095c": "r", "\u095d": "rh", "\u095e": "f"
}

def devanagari_to_hinglish(text: str) -> str:
    if not text:
        return ""
    words = text.split(" ")
    out_words = []
    for word in words:
        cleaned = word.strip(".,!?;:\"'")
        punct = word[len(cleaned):] if word.endswith((".", ",", "!", "?", ";", ":")) else ""
        if cleaned in COMMON_REPLACEMENTS:
            out_words.append(COMMON_REPLACEMENTS[cleaned] + punct)
            continue
            
        if not any("\u0900" <= c <= "\u097f" for c in word):
            out_words.append(word)
            continue
            
        res = []
        i = 0
        n = len(word)
        while i < n:
            c = word[i]
            if c in VOWELS:
                res.append(VOWELS[c])
            elif c in CONSONANTS:
                base = CONSONANTS[c]
                if i + 1 < n and word[i+1] in MATRAS:
                    res.append(base + MATRAS[word[i+1]])
                    i += 1
                elif i + 1 < n and word[i+1] == "\u094d":
                    res.append(base)
                    i += 1
                else:
                    if i + 1 == n or not ("\u0900" <= word[i+1] <= "\u097f"):
                        res.append(base)
                    elif i + 1 < n and word[i+1] in CONSONANTS:
                        res.append(base + "a")
                    else:
                        res.append(base)
            elif c in ("\u0902", "\u0901"):
                res.append("n")
            elif c in ("\u0964", "\u0965"):
                res.append(".")
            else:
                res.append(c)
            i += 1
        out_words.append("".join(res))
    return " ".join(out_words)
