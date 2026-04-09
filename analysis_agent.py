import json

class AnalysisAgent:
    def identify_strengths_and_weaknesses(self, attempts):
        """Analyze historical topic-wise performance"""
        topic_mastery = {} # {topic: [percentages]}
        
        for attempt in attempts:
            if attempt.get('topic_performance'):
                try:
                    perfs = json.loads(attempt['topic_performance'])
                    for p in perfs:
                        topic = p['topic']
                        if topic not in topic_mastery:
                            topic_mastery[topic] = []
                        topic_mastery[topic].append(p['percentage'])
                except:
                    continue
        
        analysis = {
            'strong_areas': [],
            'weak_areas': [],
            'learning_path': []
        }
        
        for topic, scores in topic_mastery.items():
            avg = sum(scores) / len(scores)
            if avg >= 75:
                analysis['strong_areas'].append({"topic": topic, "score": round(avg, 1)})
            else:
                analysis['weak_areas'].append({"topic": topic, "score": round(avg, 1)})
        
        # Sort weak areas by score (lowest first) to prioritize learning path
        analysis['weak_areas'].sort(key=lambda x: x['score'])
        
        return analysis

    def generate_mentoring(self, analysis, questions_session):
        """Generate specific revision advice based on missed questions and pages"""
        recommendations = []
        
        # Priority: Weak areas from the analysis
        for weak in analysis['weak_areas'][:3]:
            # Try to find relevant pages from the recent session if available
            relevant_pages = set()
            for q in questions_session:
                if q.get('topic') == weak['topic'] and q.get('page'):
                    relevant_pages.add(q.get('page'))
            
            pages_str = f"pages {', '.join(map(str, sorted(list(relevant_pages))))}" if relevant_pages else "the study material"
            recommendations.append({
                "topic": weak['topic'],
                "advice": f"You scored {weak['score']}% in {weak['topic']}. We recommend revising {pages_str}.",
                "priority": "High"
            })
            
        return recommendations

analysis_agent = AnalysisAgent()
