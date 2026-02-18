"""
Quiz Generator Service

RAG-based quiz generation combining static textbooks and current affairs.
Reuses patterns from ArticleGenerationService for consistency.

Key Features:
- Dual-source chunk retrieval (static + CA)
- UPSC-authentic question formats (multi-statement, assertion-reasoning)
- Detailed explanations with source citations
- Groq LLM integration for generation
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from groq import Groq
from django.conf import settings

from engines.content.models import Chunk
from engines.current_affairs.models import CAChunk
from engines.knowledge.models import Topic, ChunkTopicMap
from engines.current_affairs.models import CATopicLink
from engines.assessment.models import Quiz, Question

logger = logging.getLogger(__name__)


class QuizGeneratorService:
    """
    Service for generating UPSC-style quizzes from chunks using RAG.
    """
    
    # Constants
    MAX_STATIC_CHUNKS = 10
    MAX_CA_CHUNKS = 5
    CA_RELEVANCE_DAYS = 60
    
    def __init__(self):
        """Initialize quiz generator with Groq client."""
        self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"
    
    def generate_quiz(
        self,
        topic_id: str,
        difficulty: str = 'medium',
        include_ca: bool = False,
        question_count: int = 10,
        user_id: Optional[int] = None
    ) -> Quiz:
        """
        Generate a complete quiz for a topic.
        
        Args:
            topic_id: UUID of target topic
            difficulty: 'easy', 'medium', or 'hard'
            include_ca: Whether to include Current Affairs (Hybrid Mode)
            question_count: Number of questions to generate (1-20)
            user_id: User requesting generation (for logging)
            
        Returns:
            Generated Quiz instance with all questions
            
        Raises:
            ValueError: If topic not found or no chunks available
            Exception: If Groq generation fails
        """
        logger.info(
            "Starting quiz generation",
            extra={
                'topic_id': topic_id,
                'difficulty': difficulty,
                'include_ca': include_ca,
                'question_count': question_count,
                'user_id': user_id
            }
        )
        
        try:
            # Step 1: Get topic
            topic = Topic.objects.get(id=topic_id)
            logger.info(f"Topic found: {topic.name}")
            
            # Step 2: Fetch chunks
            static_chunks = self._fetch_static_chunks(topic)
            ca_chunks = self._fetch_ca_chunks(topic) if include_ca else []
            
            if not static_chunks and not ca_chunks:
                raise ValueError(f"No chunks available for topic: {topic.name}")
            
            logger.info(
                f"Chunks fetched - Static: {len(static_chunks)}, CA: {len(ca_chunks)}"
            )
            
            # Step 3: Build RAG context
            context = self._build_context(static_chunks, ca_chunks, include_ca)
            
            # Step 4: Generate questions via Groq
            questions_data = self._generate_questions_with_groq(
                context=context,
                topic_name=topic.name,
                difficulty=difficulty,
                question_count=question_count,
                include_ca=include_ca
            )
            
            # Step 5: Create quiz and questions in database
            quiz = self._create_quiz_in_db(
                topic=topic,
                questions_data=questions_data,
                static_chunks=static_chunks,
                ca_chunks=ca_chunks,
                difficulty=difficulty,
                include_ca=include_ca
            )
            
            logger.info(
                f"Quiz generated successfully: {quiz.id}",
                extra={
                    'quiz_id': str(quiz.id),
                    'question_count': len(questions_data)
                }
            )
            
            return quiz
            
        except Topic.DoesNotExist:
            logger.error(f"Topic not found: {topic_id}")
            raise ValueError(f"Topic with ID {topic_id} not found")
            
        except Exception as e:
            logger.error(
                f"Quiz generation failed: {str(e)}",
                extra={'topic_id': topic_id},
                exc_info=True
            )
            raise
    
    def _fetch_static_chunks(self, topic: Topic) -> List[Chunk]:
        """
        Fetch static (textbook) chunks mapped to topic.
        
        Args:
            topic: Target Topic instance
            
        Returns:
            List of Chunk instances ordered by relevance
        """
        # Get chunk IDs via ChunkTopicMap (Knowledge Engine)
        chunk_ids = ChunkTopicMap.objects.filter(
            topic=topic
        ).order_by('-relevance_score')[:self.MAX_STATIC_CHUNKS].values_list(
            'chunk_id', flat=True
        )
        
        # Fetch actual chunks
        chunks = Chunk.objects.filter(
            id__in=chunk_ids,
            source_type='static',
            quality_flag__in=['high', 'medium']
        ).select_related('document').order_by('chunk_index')
        
        return list(chunks)
    
    def _fetch_ca_chunks(self, topic: Topic) -> List[CAChunk]:
        """
        Fetch recent Current Affairs chunks linked to topic.
        
        Args:
            topic: Target Topic instance
            
        Returns:
            List of CAChunk instances from last 60 days, ordered by relevance
        """
        # Calculate cutoff date (60 days ago)
        cutoff_date = timezone.now() - timedelta(days=self.CA_RELEVANCE_DAYS)
        
        # Get CA chunk IDs via CATopicLink
        ca_chunk_ids = CATopicLink.objects.filter(
            topic=topic,
            ca_chunk__published_at__gte=cutoff_date,
            ca_chunk__is_expired=False
        ).order_by('-relevance_score')[:self.MAX_CA_CHUNKS].values_list(
            'ca_chunk_id', flat=True
        )
        
        # Fetch actual CA chunks
        ca_chunks = CAChunk.objects.filter(
            id__in=ca_chunk_ids,
            quality_flag__in=['high', 'medium']
        ).select_related('ca_article__source').order_by('-published_at')
        
        return list(ca_chunks)
    
    def _build_context(
        self,
        static_chunks: List[Chunk],
        ca_chunks: List[CAChunk],
        include_ca: bool
    ) -> str:
        """
        Build RAG context from chunks.
        
        Mimics ArticleGenerationService._assemble_context for consistency.
        
        Args:
            static_chunks: List of static Chunk instances
            ca_chunks: List of CAChunk instances
            include_ca: Whether CA chunks are included
            
        Returns:
            Formatted context string with sections
        """
        context_parts = []
        
        # Section 1: Theoretical Foundation (Static Chunks)
        if static_chunks:
            context_parts.append("=== THEORETICAL FOUNDATION (TEXTBOOK KNOWLEDGE) ===\n")
            
            for idx, chunk in enumerate(static_chunks, 1):
                source_info = f"[Source: {chunk.document.title}"
                if chunk.page_number:
                    source_info += f", Page {chunk.page_number}"
                if chunk.chapter_name:
                    source_info += f", Chapter: {chunk.chapter_name}"
                source_info += "]"
                
                context_parts.append(f"\n[Chunk {idx}] {source_info}")
                context_parts.append(chunk.chunk_text)
                context_parts.append("---")
        
        # Section 2: Current Developments (CA Chunks)
        if include_ca and ca_chunks:
            context_parts.append("\n=== CURRENT DEVELOPMENTS (RECENT NEWS) ===\n")
            
            for idx, ca_chunk in enumerate(ca_chunks, 1):
                source_info = f"[Source: {ca_chunk.ca_article.source.name}"
                source_info += f" - '{ca_chunk.ca_article.title}'"
                source_info += f", Published: {ca_chunk.published_at.strftime('%d %b %Y')}]"
                
                context_parts.append(f"\n[CA Chunk {idx}] {source_info}")
                context_parts.append(ca_chunk.chunk_text)
                context_parts.append("---")
        
        return "\n".join(context_parts)
    
    def _generate_questions_with_groq(
        self,
        context: str,
        topic_name: str,
        difficulty: str,
        question_count: int,
        include_ca: bool
    ) -> List[Dict[str, Any]]:
        """
        Generate questions using Groq LLM with batching to avoid token limits.
        
        Args:
            context: RAG context assembled from chunks
            topic_name: Name of topic for contextual prompting
            difficulty: 'easy', 'medium', or 'hard'
            question_count: Total questions to generate
            include_ca: Whether CA is included
            
        Returns:
            List of question dictionaries
        """
        all_questions = []
        BATCH_SIZE = 5
        generated_count = 0
        
        logger.info(f"Starting batched generation for {question_count} questions")
        
        # Loop until we have enough questions
        while generated_count < question_count:
            # Determine size of current batch
            remaining = question_count - generated_count
            current_batch_size = min(BATCH_SIZE, remaining)
            
            logger.info(f"Generating batch: {current_batch_size} questions (Progress: {generated_count}/{question_count})")
            
            try:
                # Build specialized prompt for this batch
                prompt = self._build_groq_prompt(
                    context=context,
                    topic_name=topic_name,
                    difficulty=difficulty,
                    question_count=current_batch_size,
                    include_ca=include_ca
                )
                
                # Call Groq API
                response = self.groq_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert UPSC question creator. Generate response in valid JSON format only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                    response_format={"type": "json_object"}
                )
                
                # Extract response text
                response_text = response.choices[0].message.content.strip()
                
                # Clean response (remove markdown if present)
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Parse JSON
                data = json.loads(response_text)
                batch_questions = data.get('questions', [])
                
                if not batch_questions:
                    logger.warning("No questions found in batch response")
                    # If we fail to get questions, avoid infinite loop
                    if current_batch_size == 1:
                         break # Give up if even 1 question fails
                    continue # Retry or proceed? proceed might result in partial quiz
                
                all_questions.extend(batch_questions)
                generated_count += len(batch_questions)
                
                logger.info(f"Batch successful. Total so far: {len(all_questions)}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for batch: {str(e)}")
                # If a batch fails, we might return partial results or fail completely
                # For now, let's stop and return what we have to avoid crashing? 
                # Or better, log and try to continue if we haven't hit limit?
                # Actually, raising error is safer than creating broken quiz
                if not all_questions:
                    raise ValueError(f"Invalid JSON from Groq: {str(e)}")
                break
                
            except Exception as e:
                logger.error(f"Groq API call failed: {str(e)}")
                if not all_questions:
                    raise
                break
                
        if not all_questions:
            raise ValueError("Failed to generate any questions")
            
        return all_questions[:question_count]
    
    def _build_groq_prompt(
        self,
        context: str,
        topic_name: str,
        difficulty: str,
        question_count: int,
        include_ca: bool
    ) -> str:
        """
        Build specialized Groq prompt for UPSC question generation.
        
        Args:
            context: RAG context
            topic_name: Topic name
            difficulty: Difficulty level
            question_count: Number of questions
            include_ca: Whether CA is included
            
        Returns:
            Complete prompt string
        """
        # Strategy varies based on mode
        if include_ca:
            strategy = """Generate UPSC-style questions that TEST THE INTERSECTION of theory and current events.

CRITICAL: Your questions MUST force students to APPLY static theoretical knowledge to analyze recent developments.

Example (Good Hybrid Question):
"Consider the following statements about Monetary Policy:
1. Repo rate is the rate at which RBI lends to commercial banks [THEORY]
2. In February 2026, RBI maintained repo rate at 6.5% citing inflation concerns [CURRENT]
3. Higher repo rates typically lead to reduced liquidity in the economy [THEORY]

Which of the above is/are correct?"

This question tests:
- Understanding of repo rate concept (from textbook)
- Awareness of current RBI policy (from news)
- Ability to connect theory to real policy decisions"""
        else:
            strategy = """Generate pure conceptual questions testing fundamental understanding from textbooks.

Focus on:
- Definitions and core concepts
- Relationships between concepts
- Application of theoretical principles
- Common misconceptions to test

Do NOT reference any recent events, dates, or current developments."""
        
        # Difficulty instructions
        difficulty_guide = {
            'easy': "Direct factual questions from single chunks. Test recall and basic understanding.",
            'medium': "Conceptual questions requiring understanding of relationships between 2-3 concepts. Test application.",
            'hard': "Complex analytical questions requiring synthesis across multiple chunks. Test critical thinking and UPSC-level reasoning."
        }
        
        difficulty_instruction = difficulty_guide.get(difficulty, difficulty_guide['medium'])
        
        # Full prompt
        prompt = f"""You are an expert UPSC Prelims question creator. Generate {question_count} multiple-choice questions about "{topic_name}".

=== CONTENT TO USE ===
{context}

=== GENERATION PARAMETERS ===
Topic: {topic_name}
Difficulty: {difficulty}
Question Count: {question_count}
Mode: {"HYBRID (Theory + Current Affairs)" if include_ca else "STATIC (Theory Only)"}

=== STRATEGY ===
{strategy}

=== DIFFICULTY CALIBRATION ===
{difficulty_instruction}

=== QUESTION TYPES TO USE ===
1. **Multi-Statement Questions** (Preferred for UPSC authenticity):
   Format: "Consider the following statements: 1. [Statement] 2. [Statement] 3. [Statement]. Which of the above is/are correct?"
   Options: Use UPSC-style options like "1 and 2 only", "2 and 3 only", "1 and 3 only", "All of the above", "None of the above"

2. **Assertion-Reasoning Questions**:
   Format: "Assertion (A): [Statement]. Reason (R): [Statement]"
   Options: 
   A) Both A and R are true and R is the correct explanation of A
   B) Both A and R are true but R is not the correct explanation of A
   C) A is true but R is false
   D) A is false but R is true

3. **Single Best Answer** (Use only when multi-statement doesn't fit):
   Format: Standard MCQ with one correct answer

=== EXPLANATION REQUIREMENTS ===
For EVERY question, provide a detailed explanation that includes:
1. **Why the correct answer is correct** (cite specific facts from chunks)
2. **Why wrong options are incorrect** (explain the misconception)
3. **Source Citations** (reference which chunks provided the information)

Format: "**Correct Answer: [X]**

**Why [X] is correct:** [Explanation citing chunk sources]

**Why other options are wrong:**
- Option [Y]: [Explanation]
- Option [Z]: [Explanation]

**Sources:** [List source chunks used]"

=== OUTPUT FORMAT ===
Return ONLY valid JSON with NO markdown formatting, NO extra text, NO preamble.

{{
  "questions": [
    {{
      "question_text": "Consider the following statements about [Topic]:\\n1. [Statement 1]\\n2. [Statement 2]\\n3. [Statement 3]\\n\\nWhich of the above is/are correct?",
      "question_type": "multi_statement",
      "statements": [
        "Statement 1 text",
        "Statement 2 text", 
        "Statement 3 text"
      ],
      "options": {{
        "A": "1 and 2 only",
        "B": "2 and 3 only",
        "C": "1 and 3 only",
        "D": "All of the above"
      }},
      "correct_answer": "B",
      "explanation": "**Correct Answer: B**\\n\\n**Why B is correct:** Statements 2 and 3 are accurate because [detailed explanation citing chunks]. Statement 1 contains an error - [explain misconception].\\n\\n**Why other options are wrong:**\\n- Option A: Includes Statement 1 which is incorrect because [reason]\\n- Option C: Includes Statement 1 which is incorrect\\n- Option D: Includes Statement 1 which is incorrect\\n\\n**Sources:** NCERT Polity Chapter 3, The Hindu (12 Feb 2026)",
      "difficulty": "{difficulty}",
      "source_chunk_indices": [0, 1, 3]
    }}
  ]
}}

=== CRITICAL RULES ===
1. Generate EXACTLY {question_count} questions
2. Each question MUST have detailed explanations with source citations
3. For multi-statement questions, provide the "statements" array
4. Use only information from the provided context
5. Ensure correct_answer is one of the option keys (A, B, C, or D)
6. Keep question_text clear and grammatically correct
7. Make distractors plausible but clearly incorrect upon analysis

Generate the {question_count} questions now:"""
        
        return prompt
    
    @transaction.atomic
    def _create_quiz_in_db(
        self,
        topic: Topic,
        questions_data: List[Dict[str, Any]],
        static_chunks: List[Chunk],
        ca_chunks: List[CAChunk],
        difficulty: str,
        include_ca: bool
    ) -> Quiz:
        """
        Create quiz and questions in database with source attribution.
        
        Args:
            topic: Topic instance
            questions_data: List of question dictionaries from Groq
            static_chunks: Source static chunks
            ca_chunks: Source CA chunks
            difficulty: Difficulty level
            include_ca: CA inclusion flag
            
        Returns:
            Created Quiz instance with all questions
        """
        # Generate quiz title
        ca_marker = " with Current Affairs" if include_ca else ""
        title = f"Quiz: {topic.name}{ca_marker}"
        
        # Calculate time limit (2 minutes per question)
        time_limit = len(questions_data) * 120
        
        # Create quiz
        quiz = Quiz.objects.create(
            title=title,
            topic=topic,
            difficulty_level=difficulty,
            include_ca=include_ca,
            question_count=len(questions_data),
            time_limit=time_limit,
            generation_metadata={
                'static_chunk_count': len(static_chunks),
                'ca_chunk_count': len(ca_chunks),
                'generated_at': timezone.now().isoformat(),
                'model': self.model
            }
        )
        
        logger.info(f"Quiz created: {quiz.id}")
        
        # Create questions
        for idx, q_data in enumerate(questions_data):
            # Create question
            question = Question.objects.create(
                quiz=quiz,
                question_text=q_data.get('question_text', ''),
                question_type=q_data.get('question_type', 'single_mcq'),
                statements=q_data.get('statements', []),
                options=q_data.get('options', {}),
                correct_answer=q_data.get('correct_answer', 'A'),
                explanation=q_data.get('explanation', ''),
                difficulty_level=q_data.get('difficulty', difficulty),
                order_index=idx
            )
            
            # Link source chunks
            # Use source_chunk_indices if provided, otherwise link all chunks
            source_indices = q_data.get('source_chunk_indices', [])
            
            if source_indices:
                # Link specific chunks
                for chunk_idx in source_indices:
                    if chunk_idx < len(static_chunks):
                        question.source_static_chunks.add(static_chunks[chunk_idx])
                    elif chunk_idx - len(static_chunks) < len(ca_chunks):
                        ca_idx = chunk_idx - len(static_chunks)
                        question.source_ca_chunks.add(ca_chunks[ca_idx])
            else:
                # Link all chunks (fallback)
                question.source_static_chunks.set(static_chunks)
                if include_ca:
                    question.source_ca_chunks.set(ca_chunks)
        
        logger.info(f"Created {len(questions_data)} questions for quiz {quiz.id}")
        
        return quiz


# Global singleton instance
_quiz_generator = None

def get_quiz_generator() -> QuizGeneratorService:
    """Get or create global quiz generator instance."""
    global _quiz_generator
    if _quiz_generator is None:
        _quiz_generator = QuizGeneratorService()
    return _quiz_generator

    