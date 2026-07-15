import re
import time
import sys
import os
import logging

logger = logging.getLogger(__name__)

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.core.models import RequestClassification, TaskCategory, ComplexityLevel
    from src.models.embedding_client import EmbeddingClient
except ImportError:
    # Fallback for direct execution
    from core.models import RequestClassification, TaskCategory, ComplexityLevel
    from models.embedding_client import EmbeddingClient

class RequestRouter:
    """
    Enhanced Request Router v2.1 with expanded category support.
    
    Classifies user requests into 9 categories:
    - code_generation (Python, Java, React, APIs, etc.)
    - web_development (HTML, CSS, JavaScript, landing pages)
    - system_design (microservices, architecture, scalability)
    - business_planning (startups, revenue, market analysis)
    - creative_writing (copy, stories, marketing content)
    - research_analysis (analysis, comparison, explanation)
    - troubleshooting (debugging, errors, fixes)
    - data_analysis (datasets, visualization, ML)
    - general (fallback)
    
    Complexity levels: trivial, simple, moderate, complex, expert
    """
    
    def __init__(self, embedder=None):
        self.embedder = embedder
        
        # ============================================================
        # EXPANDED CATEGORY KEYWORD DEFINITIONS
        # ============================================================
        
        self.category_patterns = {
            'code_generation': {
                'keywords': [
                    # Programming languages
                    'python', 'javascript', 'java', 'c\+\+', 'rust', 'go', 'ruby',
                    'php', 'swift', 'kotlin', 'scala', 'r', 'matlab',
                    'typescript', 'assembly', 'bash', 'powershell',
                    # Actions
                    'write', 'create', 'build', 'implement', 'develop', 'code',
                    'program', 'script', 'function', 'method', 'class', 'module',
                    'algorithm', 'data structure', 'logic',
                    # Web/backend specific
                    'api', 'rest', 'graphql', 'endpoint', 'route', 'handler',
                    'controller', 'service', 'repository', 'model', 'schema',
                    'database', 'sql', 'nosql', 'mongodb', 'postgresql', 'redis',
                    'docker', 'kubernetes', 'deploy', 'compile', 'debug', 'test',
                    # Specific patterns
                    'factorial', 'fibonacci', 'sorting', 'recursion', 'loop',
                    'crud', 'authentication', 'authorization', 'oauth', 'jwt'
                ],
                'patterns': [
                    r'\b(write|create|build|implement|code)\s+(a\s+)?(python|java|javascript|c\+\+|rust|go|function|method|class|program|script|app|application)\b',
                    r'\b(def|function|class|const|let|var|import|#include|from)\b',
                    r'\b(api|endpoint|route|handler|controller|service|repository)\b',
                    r'\b(sql|query|select|insert|update|delete|table|schema|migrate)\b',
                ],
                'weight': 1.0,
                'description': 'Writing code, building applications, algorithms'
            },
            
            'web_development': {
                'keywords': [
                    'website', 'webpage', 'landing page', 'frontend', 'backend',
                    'html', 'css', 'javascript', 'responsive', 'mobile-friendly',
                    'component', 'ui', 'ux', 'design', 'button', 'form',
                    'dom', 'element', 'style', 'animation', 'scroll',
                    'wordpress', 'shopify', 'nextjs', 'nuxt', 'gatsby', 'vue',
                    'react', 'angular', 'svelte', 'tailwind', 'bootstrap',
                    'sass', 'less', 'webpack', 'vite', 'parcel'
                ],
                'patterns': [
                    r'\b(website|webpage|landing\s*page|front\s*end|back\s*end)\b',
                    r'\b(html|css|responsive|mobile[\s-]?friendly)\b',
                    r'\b(component|ui|ux|user\s*interface)\b',
                    r'\b(react|angular|vue|svelte|nextjs|nuxt)\b',
                ],
                'weight': 1.0,
                'description': 'Web pages, front-end/back-end development'
            },
            
            'system_design': {
                'keywords': [
                    'architecture', 'microservices', 'monolith', 'distributed',
                    'scalability', 'throughput', 'latency', 'availability',
                    'system', 'platform', 'infrastructure', 'cloud',
                    'aws', 'azure', 'gcp', 'kubernetes', 'docker', 'container',
                    'load balancer', 'cache', 'queue', 'message broker',
                    'database design', 'schema', 'data flow', 'service boundary',
                    'api gateway', 'service mesh', 'event-driven', 'cqrs', 'saga',
                    'pattern', 'omnifigent', 'hexagonal', 'clean architecture'
                ],
                'patterns': [
                    r'\b(architecture|microservices?|distributed\s*system|design\s*a)\b',
                    r'\b(scalab(le|ility)|throughput|latency|availab(ility|le))\b',
                    r'\b(aws|azure|gcp|kubernetes?|docker|container)\b',
                    r'\b(load\s*balanc(er|ing)|cache|queue|message\s*broker)\b',
                ],
                'weight': 1.0,
                'description': 'System architecture, distributed systems, infrastructure'
            },
            
            'business_planning': {
                'keywords': [
                    'business', 'startup', 'company', 'revenue', 'profit',
                    'market', 'customer', 'client', 'stakeholder', 'investor',
                    'strategy', 'roadmap', 'milestone', 'funding', 'pitch',
                    'marketing', 'sales', 'pricing', 'subscription', 'freemium',
                    'competitor', 'analysis', 'swot', 'business model',
                    'plan', 'proposal', 'executive summary', 'board deck',
                    'mvp', 'product-market fit', 'value proposition', 'unit economics'
                ],
                'patterns': [
                    r'\b(business\s*(plan|model|strategy)|startup|revenue\s*model)\b',
                    r'\b(market\s*(analysis|research)|competitive\s*(landscape|analysis))\b',
                    r'\b(roadmap|pitch\s*deck|executive\s*summary|board\s*deck)\b',
                    r'\b(help\s+me\s+with\s+marketing|marketing\s*(strategy|plan|campaign))\b',
                ],
                'weight': 1.0,
                'description': 'Business strategy, planning, startups, go-to-market'
            },
            
            'creative_writing': {
                'keywords': [
                    'write', 'story', 'poem', 'essay', 'article', 'blog post',
                    'copy', 'content', 'headline', 'tagline', 'slogan',
                    'script', 'dialogue', 'character', 'narrative', 'plot',
                    'email', 'raise', 'salary', 'boss', 'manager',
                    'newsletter', 'social media', 'post', 'tweet',
                    'creative', 'imaginative', 'compelling', 'engaging',
                    'marketing', 'campaign', 'brand', 'audience', 'advertising',
                    'shakespeare', 'sonnet', 'haiku', 'lyrics', 'prose',
                    'fiction', 'non-fiction', 'memoir', 'biography'
                ],
                'patterns': [
                    r'\b(story|poem|essay|article|blog\s*post|copywriting?)\b',
                    r'\b(email\s*(sequence|campaign|newsletter)|social\s*media)\b',
                    r'\b(headline|tagline|slogan|creative\s*writing)\b',
                ],
                'weight': 1.0,
                'description': 'Creative content, copywriting, storytelling'
            },
            
            'research_analysis': {
                'keywords': [
                    'research', 'analyze', 'analysis', 'study', 'investigate',
                    'compare', 'contrast', 'evaluate', 'assess', 'critique',
                    'report', 'paper', 'thesis', 'dissertation', 'literature',
                    'hypothesis', 'experiment', 'data', 'statistics',
                    'ethical', 'implication', 'impact', 'trend', 'finding',
                    'explain', 'why', 'how does', 'what is the difference',
                    'pros and cons', 'advantages vs disadvantages',
                    'history of', 'evolution of', 'future of'
                ],
                'patterns': [
                    r'\b(research|analyze|analysis|study|investigate)\b',
                    r'\b(compare|contrast|evaluate|assess|critique)\b',
                    r'\b(ethical\s*(implication|impact|concern)|critical\s*analysis)\b',
                    r'\b(explain\s*(why|how|what)\b',
                ],
                'weight': 1.0,
                'description': 'Research, analysis, explanation, comparison'
            },
            
            'troubleshooting': {
                'keywords': [
                    'fix', 'error', 'bug', 'issue', 'problem', 'broken',
                    'not working', 'fail', 'crash', 'debug', 'resolve',
                    'why is', 'how do i', 'i can\'t',
                    'exception', 'warning', 'stack trace', '404', '500',
                    'configuration', 'setup', 'install', 'upgrade', 'migrate',
                    'slow', 'timeout', 'connection refused', 'forbidden'
                ],
                'patterns': [
                    r'\b(fix|debug|resolve|troubleshoot)\b',
                    r'\b(error|bug|issue|problem|exception)\b',
                    r'\b(not\s*working|broken|fail(ed|ing)?)\b',
                    r'\b(why\s*is|how\s*do\s*i|i\s*can\'t)\b',
                ],
                'weight': 1.0,
                'description': 'Debugging, error resolution, technical support'
            },
            
            'data_analysis': {
                'keywords': [
                    'data', 'dataset', 'csv', 'excel', 'spreadsheet',
                    'analyze data', 'visualization', 'chart', 'graph', 'dashboard',
                    'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly',
                    'statistics', 'regression', 'classification', 'clustering',
                    'ml', 'machine learning', 'ai', 'model', 'prediction',
                    'etl', 'pipeline', 'transform', 'clean', 'wrangle',
                    'tableau', 'power bi', 'looker', 'grafana', 'kibana'
                ],
                'patterns': [
                    r'\b(data\s*(analysis|set|frame|visualization|cleaning|wrangling))\b',
                    r'\b(pandas|numpy|matplotlib|jupyter|notebook)\b',
                    r'\b(machine\s*learning|ml\s*model|statistical\s*analysis)\b',
                ],
                'weight': 1.0,
                'description': 'Data science, visualization, analytics, ML'
            }
        }
        
        # ============================================================
        # COMPLEXITY INDICATORS
        # ============================================================
        
        self.complexity_indicators = {
            'trivial': {
                'max_words': 15,
                'examples': ['hello world', 'print name', 'add two numbers'],
                'indicators': []
            },
            'simple': {
                'max_words': 35,
                'keywords': ['simple', 'basic', 'quick', 'short', 'small', 'single function'],
                'indicators': ['single function', 'one class', 'basic feature']
            },
            'moderate': {
                'max_words': 80,
                'keywords': ['application', 'system', 'multiple', 'integrate', 'api', 'database'],
                'indicators': ['multiple functions', 'database involved', 'user input', 'authentication']
            },
            'complex': {
                'max_words': 150,
                'keywords': ['architecture', 'distributed', 'scale', 'enterprise', 'production', 'real-time'],
                'indicators': ['microservices', 'multiple services', 'high concurrency', 'message queue']
            },
            'expert': {
                'max_words': float('inf'),
                'keywords': ['enterprise', 'mission-critical', 'high availability', 'fault tolerant', 'disaster recovery'],
                'indicators': ['multi-region', 'compliance', 'security audit', 'pci dss', 'hipaa']
            }
        }

    def _count_keyword_matches(self, text, keywords):
        """Count how many keywords appear in text (case-insensitive)"""
        text_lower = text.lower()
        count = 0
        matched = []
        for kw in keywords:
            if kw.lower() in text_lower:
                count += 1
                matched.append(kw)
        return count, matched

    def _check_regex_patterns(self, text, patterns):
        """Check if any regex pattern matches the text"""
        matches = []
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(pattern)
            except re.error:
                pass
        return len(matches), matches

    def _classify_by_keywords(self, text):
        """
        Primary classification strategy: Keyword + Pattern matching.
        Returns dict of category -> score
        """
        scores = {}
        
        for category, config in self.category_patterns.items():
            score = 0
            
            # Count keyword matches
            kw_count, matched_kws = self._count_keyword_matches(text, config['keywords'])
            score += kw_count * 10  # Weighted heavily
            
            # Check regex patterns
            pattern_count, matched_patterns = self._check_regex_patterns(text, config['patterns'])
            score += pattern_count * 20  # Patterns are strong indicators
            
            # Apply category weight
            score *= config.get('weight', 1.0)
            
            if score > 0:
                scores[category] = {
                    'score': score,
                    'keyword_matches': kw_count,
                    'pattern_matches': pattern_count,
                    'matched_keywords': matched_kws[:5],  # Top 5 for logging
                    'description': config.get('description', '')
                }
        
        return scores

    def _classify_by_embedding(self, text, top_n=3):
        """
        Fallback classification: Use embedding similarity against known examples.
        Only called if keyword matching is inconclusive.
        """
        if not self.embedder:
            return {}
        
        try:
            # Category example queries for similarity search
            category_examples = {
                'code_generation': 'Write a Python function to implement binary search algorithm with proper error handling',
                'web_development': 'Build a responsive landing page with React, Tailwind CSS, and dark mode toggle',
                'system_design': 'Design microservices architecture for e-commerce platform handling 10k concurrent users',
                'business_planning': 'Create comprehensive business plan for AI tutoring startup with market analysis and funding requirements',
                'creative_writing': 'Write compelling marketing copy for new smart water bottle product launch campaign',
                'research_analysis': 'Analyze ethical implications of large language models on society with balanced arguments',
                'troubleshooting': 'Debug Flask authentication error returning 401 unauthorized after token refresh',
                'data_analysis': 'Visualize sales dataset trends using pandas, matplotlib with interactive Plotly dashboard'
            }
            
            similarities = {}
            query_embedding = self.embedder.embed(text)
            
            for category, example in category_examples.items():
                example_embedding = self.embedder.embed(example)
                
                # Simple cosine similarity (dot product for normalized embeddings)
                if len(query_embedding) == len(example_embedding):
                    dot_product = sum(q * e for q, e in zip(query_embedding, example_embedding))
                    similarities[category] = dot_product
            
            # Return top N categories by similarity
            sorted_cats = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_n]
            return {cat: {'score': sim * 100, 'method': 'embedding'} for cat, sim in sorted_cats}
            
        except Exception as e:
            print(f"[Router] Embedding classification failed: {e}")
            return {}

    def _assess_complexity(self, text, category_scores):
        """
        Assess request complexity using multiple heuristics.
        """
        words = len(text.split())
        chars = len(text)
        
        # Base complexity from length
        if words <= 15:
            base_level = ComplexityLevel.TRIVIAL
            base_score = 1
        elif words <= 35:
            base_level = ComplexityLevel.SIMPLE
            base_score = 2
        elif words <= 80:
            base_level = ComplexityLevel.MODERATE
            base_score = 3
        elif words <= 150:
            base_level = ComplexityLevel.COMPLEX
            base_score = 4
        else:
            base_level = ComplexityLevel.EXPERT
            base_score = 5
        
        # Complexity boosters (increase level)
        boosters = {
            'expert': [
                'enterprise', 'production', 'mission.critical', 'high availability',
                'fault.tolerant', 'disaster.recovery', 'multi.region', 'compliance',
                'security audit', 'pci', 'hipaa', 'gdpr', 'encryption at rest',
                'sharding', 'replication', 'event.sourcing', 'cqrs', 'saga',
                'zero.downtime', '99.9% uptime', 'sla', 'failover'
            ],
            'complex': [
                'microservices?', 'distributed', 'scale', 'concurrency',
                'real.time', 'async', 'message queue', 'kafka', 'rabbitmq',
                'kubernetes', 'docker', 'container', 'orchestration',
                'load balancer', 'cdn', 'caching strategy', 'index optimization',
                'event.driven', ' eventual consistency', 'cap theorem'
            ],
            'moderate': [
                'authentication', 'authorization', 'oauth', 'jwt', 'session',
                'database', 'sql', 'orm', 'migration', 'seed data',
                'api', 'rest', 'crud', 'validation', 'error handling',
                'testing', 'unit test', 'integration', 'ci/cd', 'deployment',
                'logging', 'monitoring', 'alerting', 'observability'
            ]
        }
        
        text_lower = text.lower()
        
        # Check for complexity booster keywords
        for level, keywords in boosters.items():
            for kw in keywords:
                if kw.replace('.', '') in text_lower.replace(' ', '.'):
                    if level == 'expert' and base_score < 5:
                        base_level = ComplexityLevel.EXPERT
                        base_score = 5
                    elif level == 'complex' and base_score < 4:
                        base_level = ComplexityLevel.COMPLEX
                        base_score = 4
                    elif level == 'moderate' and base_score < 3:
                        base_level = ComplexityLevel.MODERATE
                        base_score = 3
        
        # Category-specific complexity adjustments
        top_category = max(category_scores.keys(), key=lambda k: category_scores[k]['score']) if category_scores else None
        
        if top_category:
            # System design always at least complex
            if top_category == 'system_design' and base_score < 4:
                base_level = ComplexityLevel.COMPLEX
                base_score = 4
            
            # Business planning with financials/strategy → at least moderate
            if top_category == 'business_planning':
                biz_indicators = ['revenue', 'funding', 'investment', 'market analysis', 'roadmap', 'financial']
                if any(ind in text_lower for ind in biz_indicators) and base_score < 3:
                    base_level = ComplexityLevel.MODERATE
                    base_score = 3
            
            # Code generation with architecture/system keywords → bump up
            if top_category == 'code_generation':
                arch_indicators = ['architecture', 'design pattern', 'framework', 'library', 'sdk', 
                                 'microservices', 'system', 'platform', 'infrastructure']
                if any(ind in text_lower for ind in arch_indicators):
                    if base_score < 4:
                        base_level = ComplexityLevel.COMPLEX
                        base_score = 4
        
        # Technical specificity check (more specific = more complex)
        tech_terms = re.findall(
            r'\b(python|javascript|java|c\+\+|rust|go|sql|nosql|redis|mongodb|docker|kubernetes|'
            r'aws|azure|gcp|api|rest|graphql|oauth|jwt|ssl|tcp/ip|http|https|ssh|ftp|smtp|imap|pop3|dns|cdn|'
            r'ssl/tls|tcp|udp|icmp|rpc|grpc|websocket|mqtt|amqp|coap)\b', 
            text_lower
        )
        if len(tech_terms) >= 5 and base_score < 4:
            base_level = ComplexityLevel.COMPLEX
            base_score = 4
        
        # Length-based override for very long requests
        if words > 200 and base_score < 5:
            base_level = ComplexityLevel.EXPERT
            base_score = 5
        
        return base_level, base_score

    def process(self, request, context):
        """
        Main entry point: Classify the request.
        
        Returns: RequestClassification with:
        - task_category: Detected category (now with 9 options!)
        - complexity_level: Assessed complexity
        - confidence_score: How confident we are (0-1)
        - reasoning_method: Which method we used
        - processing_time_ms: How long it took
        """
        start = time.time()
        
        # Step 1: Try keyword-based classification (primary method)
        keyword_scores = self._classify_by_keywords(request)
        
        # Step 2: If keyword matching is weak or inconclusive, try embedding fallback
        if not keyword_scores or max(s['score'] for s in keyword_scores.values()) < 20:
            embedding_scores = self._classify_by_embedding(request)
            
            # Merge scores (keyword gets priority)
            for cat, score_data in embedding_scores.items():
                if cat not in keyword_scores:
                    keyword_scores[cat] = score_data
                else:
                    # Boost existing score slightly with embedding evidence
                    keyword_scores[cat]['score'] += score_data['score'] * 0.3
        
        # BUG 3 FIX: Pre-filter for obvious non-code categories BEFORE scoring
        # This prevents "help me with marketing" or "write me a raise email"
        # from being misclassified as code_generation.
        text_lower = request.lower()
        _HIGH_CONFIDENCE_RULES = [
            # Email/writing tasks that should never be code
            (['email', 'raise', 'salary', 'resignation', 'cover letter', 'thank you', 'apology'], 'creative_writing'),
            # Marketing/business tasks
            (['marketing', 'campaign', 'brand', 'audience', 'advertising', 'social media'], 'business_planning'),
            # Academic/research tasks
            (['essay', 'thesis', 'dissertation', 'research paper', 'literature review'], 'research_analysis'),
            # Creative writing
            (['story', 'poem', 'novel', 'script', 'song', 'haiku', 'fiction'], 'creative_writing'),
        ]
        for trigger_words, forced_category in _HIGH_CONFIDENCE_RULES:
            if any(w in text_lower for w in trigger_words):
                # Only force if code_generation isn't VERY confident (pattern match)
                code_score = keyword_scores.get('code_generation', {}).get('score', 0)
                # Pattern matches (worth 20 each) are strong signals for code
                code_pattern_matches = keyword_scores.get('code_generation', {}).get('pattern_matches', 0)
                # If code has no pattern matches and only generic keyword matches, override
                if code_pattern_matches == 0:
                    keyword_scores[forced_category] = keyword_scores.get(forced_category, {'score': 0, 'pattern_matches': 0, 'keyword_matches': 0, 'matched_keywords': [], 'description': ''})
                    keyword_scores[forced_category]['score'] = max(keyword_scores[forced_category]['score'], 30)
                    if forced_category in keyword_scores and 'matched_keywords' in keyword_scores[forced_category]:
                        for w in trigger_words:
                            if w in text_lower and w not in keyword_scores[forced_category].get('matched_keywords', []):
                                keyword_scores[forced_category]['matched_keywords'] = keyword_scores[forced_category].get('matched_keywords', []) + [w]
                                keyword_scores[forced_category]['score'] += 10

        # Step 3: Determine best category
        if keyword_scores:
            # Sort by score descending
            sorted_categories = sorted(keyword_scores.items(), 
                                      key=lambda x: x[1]['score'], 
                                      reverse=True)
            
            best_category_name = sorted_categories[0][0]
            best_score = sorted_categories[0][1]['score']
            
            # BUG 3 FIX: If top category is code_generation but confidence would be < 0.70,
            # check if the second-best category is more appropriate
            if best_category_name == 'code_generation' and len(sorted_categories) > 1:
                # Calculate what confidence would be
                score_gap = best_score - sorted_categories[1][1]['score']
                potential_confidence = min(0.95, 0.6 + (score_gap / 100))
                if potential_confidence < 0.70:
                    # Low confidence code classification -- likely wrong
                    # Promote the second-best if it has a reasonable score
                    second_name = sorted_categories[1][0]
                    if second_name != 'code_generation' and sorted_categories[1][1]['score'] >= 10:
                        best_category_name = second_name
                        best_score = sorted_categories[1][1]['score']
                        logger.info(f"Router: Overriding code_generation (conf {potential_confidence:.2f}) with {second_name}")

            # Map string category to NEW expanded enum
            category_map = {
                'code_generation': TaskCategory.CODE_GEN,
                'web_development': TaskCategory.WEB_DEV,
                'system_design': TaskCategory.SYSTEM_DESIGN,
                'business_planning': TaskCategory.BUSINESS,
                'creative_writing': TaskCategory.CREATIVE,
                'research_analysis': TaskCategory.RESEARCH,
                'troubleshooting': TaskCategory.TROUBLESHOOTING,
                'data_analysis': TaskCategory.DATA_ANALYSIS,
                'general': TaskCategory.GENERAL
            }
            
            task_category = category_map.get(best_category_name, TaskCategory.GENERAL)
            
            # Calculate confidence based on score gap between #1 and #2
            if len(sorted_categories) > 1:
                score_gap = best_score - sorted_categories[1][1]['score']
                confidence = min(0.95, 0.6 + (score_gap / 100))
            else:
                confidence = min(0.95, 0.6 + (best_score / 200))
            
            # Log what we detected (DETAILED LOGGING!)
            matched_kws = sorted_categories[0][1].get('matched_keywords', [])
            desc = sorted_categories[0][1].get('description', '')
            print(f"[Router] ═══════════════════════════════════════")
            print(f"[Router] 📊 CATEGORY DETECTED: {best_category_name}")
            print(f"[Router] 🎯 Confidence: {confidence:.2f} | Score: {best_score:.1f}")
            f"[Router] 🔑 Keywords: {', '.join(matched_kws[:8])}"
            if desc:
                print(f"[Router] 💡 Context: {desc}")
            print(f"[Router] ═══════════════════════════════════════")
            
        else:
            # Fallback to general
            task_category = TaskCategory.GENERAL
            confidence = 0.5
            print("[Router] ⚠️ No category detected, defaulting to GENERAL")
        
        # Step 4: Assess complexity
        complexity_level, complexity_score = self._assess_complexity(request, keyword_scores)
        
        elapsed = (time.time() - start) * 1000
        
        result = RequestClassification(
            task_category=task_category,
            complexity_level=complexity_level,
            confidence_score=confidence,
            reasoning_method="enhanced_keyword_pattern_matching_v2.1",
            processing_time_ms=elapsed,
            metadata={
                'raw_text_length': len(request),
                'word_count': len(request.split()),
                'detected_category': best_category_name if keyword_scores else 'general',
                'all_scores': {k: v['score'] for k, v in keyword_scores.items()} if keyword_scores else {},
                'complexity_breakdown': {
                    'word_count': len(request.split()),
                    'base_level': complexity_level.value,
                    'adjusted_score': complexity_score,
                    'reasoning': 'Based on keyword/regex matching + heuristics'
                }
            }
        )
        
        print(f"[Router] ✅ FINAL: {task_category.value} | {complexity_level.value} | conf:{confidence:.2f} [{elapsed:.0f}ms]")
        
        return result

    def validate_input(self, input_data):
        """Validate that input is non-empty string"""
        return isinstance(input_data, str) and len(input_data.strip()) > 0

    def get_stage_info(self):
        return {"name": "Enhanced Request Router v2.1", "stage": 1, "version": "2.1", "categories": 9}
