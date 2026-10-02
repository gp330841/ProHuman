import random

# A rich corpus of realistic meeting data
SCENARIO_TEMPLATES = [
    {
        "meeting_type": "sprint_planning",
        "typical_duration_minutes": 45,
        "typical_speaker_count": 5,
        "topic_pool": ["Jira board review", "capacity planning", "carry-over tasks", "epic estimation"],
        "dialogue_patterns": [
            [
                {"role": "manager", "text": "Alright everyone, let's look at the sprint backlog. We have a lot of carry-over from last week.", "duration_sec": 5},
                {"role": "engineer", "text": "Yeah, the database migration took way longer than expected. I'm almost done though.", "duration_sec": 4},
                {"role": "manager", "text": "Okay, so how many story points can you commit to for this sprint?", "duration_sec": 3},
                {"role": "engineer", "text": "I can probably do 8 points, assuming no production incidents.", "duration_sec": 3},
                {"role": "designer", "text": "I need some dev time for the new onboarding flow.", "duration_sec": 3},
                {"role": "manager", "text": "I'll take that action item to coordinate between you two. Let's follow up tomorrow.", "duration_sec": 4}
            ]
        ]
    },
    {
        "meeting_type": "design_review",
        "typical_duration_minutes": 30,
        "typical_speaker_count": 3,
        "topic_pool": ["Figma mockups", "UX feedback", "accessibility"],
        "dialogue_patterns": [
            [
                {"role": "designer", "text": "So here is the updated Figma file for the user profile page. Notice the new color scheme.", "duration_sec": 6},
                {"role": "engineer", "text": "Looks good, but the contrast ratio on that button might be too low.", "duration_sec": 4},
                {"role": "designer", "text": "Good catch, I'll update it to meet AA standards. Deadline is Friday for the final handoff.", "duration_sec": 5},
                {"role": "product_manager", "text": "Can we also add a tooltip for the settings icon?", "duration_sec": 3},
                {"role": "designer", "text": "Sure, I'll add that to the mockup right now.", "duration_sec": 3}
            ]
        ]
    },
    {
        "meeting_type": "incident_postmortem",
        "typical_duration_minutes": 60,
        "typical_speaker_count": 4,
        "topic_pool": ["root cause analysis", "mitigation steps", "action items"],
        "dialogue_patterns": [
            [
                {"role": "manager", "text": "Let's review what happened during the outage yesterday.", "duration_sec": 4},
                {"role": "engineer", "text": "The primary database hit 100% CPU because of an unoptimized query in the new feature release.", "duration_sec": 7},
                {"role": "engineer2", "text": "We should have caught that in staging. We need better load testing.", "duration_sec": 5},
                {"role": "manager", "text": "Agreed. I'll take that as an action item. Let's add load testing to the CI pipeline.", "duration_sec": 6},
                {"role": "engineer", "text": "I'll create the Jira ticket for it.", "duration_sec": 3}
            ]
        ]
    },
    {
        "meeting_type": "stakeholder_update",
        "typical_duration_minutes": 30,
        "typical_speaker_count": 2,
        "topic_pool": ["project status", "budget", "risks"],
        "dialogue_patterns": [
            [
                {"role": "project_manager", "text": "The Q3 roadmap is mostly on track, but we're seeing some delays in the mobile app release.", "duration_sec": 7},
                {"role": "stakeholder", "text": "What's the main blocker?", "duration_sec": 2},
                {"role": "project_manager", "text": "Waiting on Apple App Store approval. Usually takes a few days.", "duration_sec": 5},
                {"role": "stakeholder", "text": "Okay, please keep me posted. Let's follow up on Monday.", "duration_sec": 4}
            ]
        ]
    },
    {
        "meeting_type": "1_on_1",
        "typical_duration_minutes": 30,
        "typical_speaker_count": 2,
        "topic_pool": ["career growth", "current projects", "blockers"],
        "dialogue_patterns": [
            [
                {"role": "manager", "text": "How's your week going? Any blockers?", "duration_sec": 3},
                {"role": "employee", "text": "Pretty good. I'm just waiting on the API team to unblock me for the dashboard feature.", "duration_sec": 6},
                {"role": "manager", "text": "Do you need me to escalate that?", "duration_sec": 3},
                {"role": "employee", "text": "Not yet, I'll ping them again today. If I don't hear back by tomorrow, I'll let you know.", "duration_sec": 6}
            ]
        ]
    },
    {
        "meeting_type": "all_hands",
        "typical_duration_minutes": 60,
        "typical_speaker_count": 6,
        "topic_pool": ["company updates", "Q&A", "new hires"],
        "dialogue_patterns": [
            [
                {"role": "ceo", "text": "Welcome everyone to our monthly all-hands. We had a record-breaking quarter.", "duration_sec": 6},
                {"role": "vp_sales", "text": "Yes, sales were up 20% compared to Q2.", "duration_sec": 4},
                {"role": "hr", "text": "And we'd like to welcome our three new engineers joining us this week.", "duration_sec": 5},
                {"role": "ceo", "text": "Let's open the floor for Q&A.", "duration_sec": 3},
                {"role": "employee", "text": "Are we still planning to return to the office next month?", "duration_sec": 4},
                {"role": "ceo", "text": "We're currently evaluating that. We'll send out a survey by Friday.", "duration_sec": 5}
            ]
        ]
    },
    {
        "meeting_type": "client_call",
        "typical_duration_minutes": 45,
        "typical_speaker_count": 3,
        "topic_pool": ["requirements gathering", "demo", "feedback"],
        "dialogue_patterns": [
            [
                {"role": "sales", "text": "Thanks for joining us today. We'd like to show you the latest demo of our platform.", "duration_sec": 6},
                {"role": "client", "text": "Great, I'm looking forward to it.", "duration_sec": 3},
                {"role": "sales", "text": "As you can see here on the dashboard, we've added the custom reporting feature you requested.", "duration_sec": 7},
                {"role": "client", "text": "This looks good. Can we export this to Excel?", "duration_sec": 4},
                {"role": "sales", "text": "Yes, I'll follow up with the documentation on how to do that.", "duration_sec": 4}
            ]
        ]
    },
    {
        "meeting_type": "brainstorming",
        "typical_duration_minutes": 45,
        "typical_speaker_count": 4,
        "topic_pool": ["new features", "marketing campaigns", "branding"],
        "dialogue_patterns": [
            [
                {"role": "facilitator", "text": "Let's brainstorm some ideas for the upcoming holiday campaign.", "duration_sec": 4},
                {"role": "marketing", "text": "We could run a social media contest with user-generated content.", "duration_sec": 5},
                {"role": "designer", "text": "I can create some festive graphics for that.", "duration_sec": 3},
                {"role": "facilitator", "text": "Great idea. I'll add that to the whiteboard. What else?", "duration_sec": 4},
                {"role": "marketing", "text": "Maybe an email newsletter highlighting our top products of the year.", "duration_sec": 5}
            ]
        ]
    }
]

NAMES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Heidi", "Ivan", "Judy", "Mallory", "Victor", "Peggy", "Trent"]

def get_random_scenario(rand: random.Random):
    return rand.choice(SCENARIO_TEMPLATES)

def generate_speakers(scenario, rand: random.Random):
    count = scenario["typical_speaker_count"]
    return rand.sample(NAMES, k=min(count, len(NAMES)))
