import requests
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

# Configure logging for translation service
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationService:
    """
    Wiktionary translation service for German-English translations.
    Uses lemmatized words and POS tags to resolve translation ambiguities.
    """
    
    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VocabHarvester/1.0 (https://github.com/martin-widmann/vocab-harvester)'
        })
    
    def _make_request(self, url: str) -> Optional[Dict]:
        """
        Make HTTP request with error handling and retry logic.
        
        Args:
            url: The URL to request
            
        Returns:
            Dictionary with response data or None if request failed
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                last_exception = f"Request timed out after {self.timeout} seconds"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_exception}")
                
            except requests.exceptions.ConnectionError:
                last_exception = "Network connection error"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_exception}")
                
            except requests.exceptions.HTTPError as e:
                last_exception = f"HTTP error {e.response.status_code}"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_exception}")
                
            except requests.exceptions.RequestException as e:
                last_exception = f"Request error: {str(e)}"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_exception}")
                
            except json.JSONDecodeError:
                last_exception = "Invalid JSON response"
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries}: {last_exception}")
                
            # Wait before retry (exponential backoff)
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
        
        logger.error(f"All {self.max_retries} attempts failed. Last error: {last_exception}")
        return None
    
    def _extract_translations(self, page_content: str, pos: str) -> List[str]:
        """
        Extract English translations from Wiktionary page content.
        
        Args:
            page_content: Raw page content from Wiktionary
            pos: Part of speech to filter translations
            
        Returns:
            List of English translations
        """
        translations = []
        import re
        
        # Method 1: Look for German translations in English section
        lines = page_content.split('\n')
        in_english_section = False
        in_translation_section = False
        
        for line in lines:
            line = line.strip()
            
            # Find English translations section
            if '==English==' in line or '== English ==' in line:
                in_english_section = True
                continue
            elif line.startswith('==') and '==' in line and in_english_section:
                in_english_section = False
                continue
                
            if in_english_section and ('===Translations===' in line or '=== Translations ===' in line):
                in_translation_section = True
                continue
            elif in_translation_section and line.startswith('==='):
                in_translation_section = False
                continue
            
            # Extract translations from the translation section
            if in_translation_section:
                # Look for German translations (simple pattern matching)
                if 'German:' in line or 'german:' in line:
                    # Extract text after "German:" 
                    german_part = line.split('German:')[1] if 'German:' in line else line.split('german:')[1]
                    # Extract words in brackets
                    matches = re.findall(r'\[\[(.*?)\]\]', german_part)
                    if matches:
                        translations.extend(matches)
        
        # Method 2: Look for German section with English translations
        if not translations:
            in_german_section = False
            for line in lines:
                line = line.strip()
                
                if '==German==' in line or '== German ==' in line:
                    in_german_section = True
                    continue
                elif line.startswith('==') and '==' in line and in_german_section:
                    in_german_section = False
                    continue
                
                if in_german_section:
                    # Look for definition lines starting with #
                    if line.startswith('#') and not line.startswith('##'):
                        # Extract English definitions
                        definition = line[1:].strip()
                        # Remove wiki markup and extract clean words
                        clean_def = re.sub(r'\[\[(.*?)\]\]', r'\1', definition)
                        clean_def = re.sub(r'{{.*?}}', '', clean_def)
                        # Split on commas and semicolons to get individual meanings
                        parts = re.split(r'[,;]', clean_def)
                        for part in parts[:3]:  # Take first 3 parts
                            part = part.strip()
                            if part and len(part.split()) <= 2 and part.isalpha():  # Simple words/phrases
                                translations.append(part)
        
        # Method 3: Fallback - look for any [[word]] patterns
        if not translations:
            all_links = re.findall(r'\[\[(.*?)\]\]', page_content)
            for link in all_links[:5]:  # Take first 5
                if '|' in link:
                    link = link.split('|')[0]  # Take the actual link, not display text
                if link and len(link.split()) <= 2 and re.match(r'^[a-zA-Z\s]+$', link):
                    translations.append(link)
        
        # Clean up translations
        cleaned_translations = []
        for trans in translations:
            trans = trans.strip().lower()
            # Remove wiki markup
            trans = re.sub(r'\[\[(.*?)\]\]', r'\1', trans)
            trans = re.sub(r'{{.*?}}', '', trans)
            # Keep only alphabetic words (including spaces for compound words)
            if trans and re.match(r'^[a-z\s]+$', trans) and len(trans) <= 20:
                cleaned_translations.append(trans)
        
        return list(set(cleaned_translations))[:5]  # Return up to 5 unique translations
    
    def get_translation(self, lemma: str, pos: str) -> Dict[str, any]:
        """
        Get translation for a single word using lemma and POS.
        
        Args:
            lemma: The lemmatized form of the word
            pos: Part of speech tag
            
        Returns:
            Dictionary containing translation data and status
        """
        if not lemma or not lemma.strip():
            return {
                'success': False,
                'error': 'Empty lemma provided',
                'translations': [],
                'lemma': lemma,
                'pos': pos
            }
        
        # Clean and encode lemma for URL
        lemma_clean = lemma.strip().lower()
        lemma_encoded = quote(lemma_clean)
        
        # Construct Wiktionary API URL
        url = f"https://en.wiktionary.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'titles': lemma_clean,
            'prop': 'revisions',
            'rvprop': 'content',
            'rvslots': 'main'
        }
        
        # Build full URL
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{url}?{param_string}"
        
        logger.info(f"Fetching translation for '{lemma_clean}' [{pos}]")
        
        # Make API request
        response_data = self._make_request(full_url)
        
        if not response_data:
            return {
                'success': False,
                'error': 'Translation failed: API error',
                'translations': [],
                'lemma': lemma,
                'pos': pos
            }
        
        try:
            # Extract page content from API response
            pages = response_data.get('query', {}).get('pages', {})
            if not pages:
                return {
                    'success': False,
                    'error': 'Translation failed: No page data found',
                    'translations': [],
                    'lemma': lemma,
                    'pos': pos
                }
            
            # Get the page content
            page = next(iter(pages.values()))
            if 'missing' in page:
                return {
                    'success': False,
                    'error': 'Translation failed: Word not found in Wiktionary',
                    'translations': [],
                    'lemma': lemma,
                    'pos': pos
                }
            
            revisions = page.get('revisions', [])
            if not revisions:
                return {
                    'success': False,
                    'error': 'Translation failed: No content available',
                    'translations': [],
                    'lemma': lemma,
                    'pos': pos
                }
            
            # Get page content
            content = revisions[0].get('slots', {}).get('main', {}).get('*', '')
            
            # Extract translations
            translations = self._extract_translations(content, pos)
            
            if not translations:
                # Try alternative: look for a simple definition or meaning
                import re
                simple_patterns = [
                    r"'''([^']+)'''",  # Bold definitions
                    r"# ([^\n]+)",      # Numbered definitions
                    r"\* ([^\n]+)"      # Bulleted definitions
                ]
                
                for pattern in simple_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        # Take first few matches and clean them
                        for match in matches[:3]:
                            clean_match = re.sub(r'\[\[([^\]]+)\]\]', r'\1', match).strip()
                            if clean_match and len(clean_match.split()) <= 3:  # Keep short definitions
                                translations.append(clean_match.lower())
                        break
            
            if translations:
                logger.info(f"Found {len(translations)} translation(s) for '{lemma_clean}'")
                return {
                    'success': True,
                    'error': None,
                    'translations': translations,
                    'lemma': lemma,
                    'pos': pos
                }
            else:
                return {
                    'success': False,
                    'error': 'Translation failed: No translations found',
                    'translations': [],
                    'lemma': lemma,
                    'pos': pos
                }
                
        except Exception as e:
            logger.error(f"Error processing translation response: {str(e)}")
            return {
                'success': False,
                'error': f'Translation failed: Processing error',
                'translations': [],
                'lemma': lemma,
                'pos': pos
            }
    
    def get_batch_translations(self, word_list: List[Tuple[str, str]]) -> List[Dict[str, any]]:
        """
        Get translations for multiple words in batch.
        
        Args:
            word_list: List of tuples (lemma, pos)
            
        Returns:
            List of translation results
        """
        if not word_list:
            return []
        
        results = []
        total = len(word_list)
        
        logger.info(f"Starting batch translation for {total} words")
        
        for i, (lemma, pos) in enumerate(word_list, 1):
            logger.info(f"Processing word {i}/{total}: {lemma}")
            result = self.get_translation(lemma, pos)
            results.append(result)
            
            # Small delay between requests to be respectful to the API
            time.sleep(0.5)
        
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Batch translation complete: {successful}/{total} successful")
        
        return results
    
    def format_translation_summary(self, translation_result: Dict[str, any]) -> str:
        """
        Format translation result for user display.
        
        Args:
            translation_result: Result from get_translation()
            
        Returns:
            Formatted string for display
        """
        if translation_result['success']:
            lemma = translation_result['lemma']
            pos = translation_result['pos']
            translations = translation_result['translations']
            
            if translations:
                trans_str = ', '.join(translations[:3])  # Show first 3 translations
                return f"{lemma} [{pos}]: {trans_str}"
            else:
                return f"{lemma} [{pos}]: (no translations found)"
        else:
            error = translation_result['error']
            lemma = translation_result['lemma']
            return f"{lemma}: {error}"


# Convenience functions for easy usage
def translate_word(lemma: str, pos: str) -> Dict[str, any]:
    """
    Convenience function to translate a single word.
    
    Args:
        lemma: The lemmatized form of the word
        pos: Part of speech tag
        
    Returns:
        Translation result dictionary
    """
    service = TranslationService()
    return service.get_translation(lemma, pos)


def translate_word_list(word_list: List[Tuple[str, str]]) -> List[Dict[str, any]]:
    """
    Convenience function to translate a list of words.
    
    Args:
        word_list: List of tuples (lemma, pos)
        
    Returns:
        List of translation results
    """
    service = TranslationService()
    return service.get_batch_translations(word_list)


def get_best_translation(lemma: str, pos: str) -> Optional[str]:
    """
    Get the best (first) translation for a word, or None if no translation found.
    
    Args:
        lemma: The lemmatized form of the word
        pos: Part of speech tag
        
    Returns:
        Best translation string or None
    """
    result = translate_word(lemma, pos)
    if result['success'] and result['translations']:
        return result['translations'][0]
    return None