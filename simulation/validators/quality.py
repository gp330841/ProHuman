from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

@dataclass
class QualityIssue:
    severity: str
    category: str
    description: str
    suggestion: str

@dataclass
class QualityScore:
    overall_score: float = 0.0
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[QualityIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

class FeatureQualityAssessor:
    def _add_issue(self, score: QualityScore, severity: str, category: str, description: str, suggestion: str):
        score.issues.append(QualityIssue(severity, category, description, suggestion))

    def assess_summary_quality(self, summary_data: Dict, transcript_segments: List[Dict]) -> QualityScore:
        score = QualityScore()
        dims = {"title": 100.0, "length": 100.0, "overlap": 100.0, "participants": 100.0}
        
        title = summary_data.get("title", "")
        if len(title) < 5 or title.lower() in ["meeting", "summary", "meeting summary"]:
            self._add_issue(score, "minor", "title", "Title is generic or too short", "Provide a more descriptive title")
            dims["title"] -= 50.0
            
        exec_sum = summary_data.get("executive_summary", "")
        if len(exec_sum) < 50 or len(exec_sum) > 500:
            self._add_issue(score, "minor", "length", "Executive summary length not ideal", "Target 50-500 characters")
            dims["length"] -= 40.0
            
        speakers = {s.get("speaker_label") for s in transcript_segments if s.get("speaker_label")}
        if summary_data.get("participant_count", 0) != len(speakers):
            self._add_issue(score, "major", "participants", "Participant count mismatch", "Ensure participant count matches unique speakers")
            dims["participants"] -= 100.0
            
        full_text = " ".join([s.get("text", "") for s in transcript_segments]).lower()
        topics = summary_data.get("key_topics", [])
        overlap_count = sum(1 for t in topics if t.lower() in full_text)
        if topics and overlap_count < len(topics) * 0.5:
             self._add_issue(score, "major", "overlap", "Key topics not found in transcript", "Extract topics strictly from transcript content")
             dims["overlap"] -= 50.0
             
        score.dimension_scores = dims
        score.overall_score = sum(dims.values()) / len(dims)
        return score

    def assess_mom_quality(self, mom_data: Dict, transcript_segments: List[Dict]) -> QualityScore:
        score = QualityScore()
        dims = {"attendees": 100.0, "decisions": 100.0, "actions": 100.0}
        
        speakers = {s.get("speaker_label") for s in transcript_segments if s.get("speaker_label")}
        attendees = set(mom_data.get("attendees", []))
        if not speakers.issubset(attendees):
             self._add_issue(score, "major", "attendees", "Missing attendees", "All speakers must be listed as attendees")
             dims["attendees"] -= 50.0
             
        full_text = " ".join([s.get("text", "") for s in transcript_segments]).lower()
        for dec in mom_data.get("decisions", []):
            dec_text = dec.get("description", str(dec)) if isinstance(dec, dict) else (getattr(dec, "description", str(dec)))
            if dec_text.lower() not in full_text: # simplified check
                self._add_issue(score, "minor", "decisions", "Decision lacks direct support", "Ensure decisions are rooted in transcript quotes")
                dims["decisions"] -= 10.0
                
        actions = set(
            a.get("description", str(a)) if isinstance(a, dict) else getattr(a, "description", str(a))
            for a in mom_data.get("action_items", [])
        )
        followups = set(
            f.get("description", str(f)) if isinstance(f, dict) else getattr(f, "description", str(f))
            for f in mom_data.get("follow_ups", [])
        )
        if actions.intersection(followups):
            self._add_issue(score, "minor", "actions", "Action and follow-up overlap", "Differentiate follow-ups from explicit action items")
            dims["actions"] -= 30.0
            
        score.dimension_scores = dims
        score.overall_score = sum(dims.values()) / len(dims) if dims else 100.0
        return score

    def assess_action_items_quality(self, action_items: List[Dict], transcript_segments: List[Dict]) -> QualityScore:
        score = QualityScore()
        dims = {"description": 100.0, "assignees": 100.0, "priority": 100.0, "unique": 100.0}
        
        speakers = {s.get("speaker_label") for s in transcript_segments if s.get("speaker_label")}
        priorities = []
        descriptions = set()
        
        for ai in action_items:
            desc = ai.get("description", "")
            if not desc or len(desc.split()) < 3:
                self._add_issue(score, "major", "description", "Unclear action item", "Provide more context with a verb")
                dims["description"] -= 20.0
                
            if desc in descriptions:
                self._add_issue(score, "minor", "unique", "Duplicate action item", "Consolidate duplicate items")
                dims["unique"] -= 20.0
            descriptions.add(desc)
            
            assignee = ai.get("assignee")
            if assignee and assignee not in speakers and assignee.lower() != "unassigned":
                self._add_issue(score, "minor", "assignees", "Unknown assignee", "Match assignees with known speakers")
                dims["assignees"] -= 20.0
                
            priorities.append(ai.get("priority", "medium"))
            
        if priorities and priorities.count("high") == len(priorities):
            self._add_issue(score, "minor", "priority", "All priorities high", "Distribute priorities more realistically")
            dims["priority"] -= 40.0
            
        score.dimension_scores = dims
        score.overall_score = max(0.0, sum(dims.values()) / len(dims))
        return score

    def assess_sentiment_quality(self, sentiment_data: Dict, transcript_segments: List[Dict]) -> QualityScore:
        score = QualityScore()
        dims = {"completeness": 100.0, "consistency": 100.0}
        
        speakers = {s.get("speaker_label") for s in transcript_segments if s.get("speaker_label")}
        
        # Handle speaker_sentiments as either list or dict
        raw_sentiments = sentiment_data.get("speaker_sentiments", [])
        if isinstance(raw_sentiments, list):
            sent_speakers = {s.get("speaker_label") for s in raw_sentiments if isinstance(s, dict)}
            indiv = [s.get("sentiment") for s in raw_sentiments if isinstance(s, dict)]
        elif isinstance(raw_sentiments, dict):
            sent_speakers = set(raw_sentiments.keys())
            indiv = [s.get("sentiment") for s in raw_sentiments.values() if isinstance(s, dict)]
        else:
            sent_speakers = set()
            indiv = []
        
        if not speakers.issubset(sent_speakers):
            self._add_issue(score, "major", "completeness", "Missing speaker sentiments", "Analyze sentiment for all active speakers")
            dims["completeness"] -= 50.0
            
        overall = sentiment_data.get("overall_sentiment")
        
        if overall == "positive" and "positive" not in indiv and indiv:
             self._add_issue(score, "minor", "consistency", "Overall sentiment contradicts individual", "Align overall sentiment with participants")
             dims["consistency"] -= 30.0
             
        score.dimension_scores = dims
        score.overall_score = sum(dims.values()) / len(dims)
        return score

    def assess_search_quality(self, search_results: List[Dict], query: str, corpus: List[Dict]) -> QualityScore:
        score = QualityScore()
        dims = {"relevance": 100.0, "duplicate": 100.0, "hybrid_ranks": 100.0}
        
        seen = set()
        for res in search_results:
            sid = res.get("segment_id")
            if sid in seen:
                 self._add_issue(score, "major", "duplicate", "Duplicate search result", "Deduplicate search results")
                 dims["duplicate"] -= 50.0
            seen.add(sid)
            
            if "vector_rank" not in res and "text_rank" not in res:
                 self._add_issue(score, "minor", "hybrid_ranks", "Missing rank data", "Populate ranks for hybrid search")
                 dims["hybrid_ranks"] -= 20.0
                 
        score.dimension_scores = dims
        score.overall_score = max(0.0, sum(dims.values()) / len(dims))
        return score
