import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import json

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from translation import TranslationService, translate_word, translate_word_list, get_best_translation


class TestTranslationService(unittest.TestCase):
    """Test cases for the TranslationService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = TranslationService(timeout=5.0, max_retries=2)
    
    def test_init(self):
        """Test TranslationService initialization."""
        service = TranslationService(timeout=10.0, max_retries=5)
        self.assertEqual(service.timeout, 10.0)
        self.assertEqual(service.max_retries, 5)
        self.assertIsNotNone(service.session)
        self.assertIn('VocabHarvester', service.session.headers['User-Agent'])
    
    @patch('translation.requests.Session.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request."""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {'test': 'data'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service._make_request('http://test.com')
        
        self.assertEqual(result, {'test': 'data'})
        mock_get.assert_called_once_with('http://test.com', timeout=5.0)
    
    @patch('translation.requests.Session.get')
    @patch('translation.time.sleep')
    def test_make_request_timeout_retry(self, mock_sleep, mock_get):
        """Test request timeout with retry logic."""
        import requests
        
        # Mock timeout on first call, success on second
        mock_get.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            Mock(json=lambda: {'success': True}, raise_for_status=lambda: None)
        ]
        
        result = self.service._make_request('http://test.com')
        
        self.assertEqual(result, {'success': True})
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)  # First retry delay
    
    @patch('translation.requests.Session.get')
    @patch('translation.time.sleep')
    def test_make_request_max_retries_exceeded(self, mock_sleep, mock_get):
        """Test request failure after max retries."""
        import requests
        
        # Mock failure on all attempts
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")
        
        result = self.service._make_request('http://test.com')
        
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 2)  # max_retries = 2
    
    @patch('translation.requests.Session.get')
    def test_make_request_http_error(self, mock_get):
        """Test HTTP error handling."""
        import requests
        
        # Mock HTTP error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        result = self.service._make_request('http://test.com')
        
        self.assertIsNone(result)
    
    def test_extract_translations_simple(self):
        """Test basic translation extraction."""
        content = '''
        ==German==
        ===Noun===
        # test translation
        # another meaning
        '''
        
        translations = self.service._extract_translations(content, 'NOUN')
        # This is a simple test - actual extraction depends on Wiktionary format
        self.assertIsInstance(translations, list)
    
    def test_extract_translations_english_section(self):
        """Test translation extraction with English section."""
        content = '''
        ==English==
        ===Translations===
        German: [[Haus]], [[Building]]
        '''
        
        translations = self.service._extract_translations(content, 'NOUN')
        self.assertIn('haus', translations)
        self.assertIn('building', translations)
    
    def test_get_translation_empty_lemma(self):
        """Test translation with empty lemma."""
        result = self.service.get_translation('', 'NOUN')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Empty lemma provided')
        self.assertEqual(result['translations'], [])
    
    @patch('translation.TranslationService._make_request')
    def test_get_translation_api_failure(self, mock_request):
        """Test translation when API request fails."""
        mock_request.return_value = None
        
        result = self.service.get_translation('haus', 'NOUN')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Translation failed: API error')
        self.assertEqual(result['translations'], [])
        self.assertEqual(result['lemma'], 'haus')
        self.assertEqual(result['pos'], 'NOUN')
    
    @patch('translation.TranslationService._make_request')
    def test_get_translation_word_not_found(self, mock_request):
        """Test translation when word is not found in Wiktionary."""
        mock_request.return_value = {
            'query': {
                'pages': {
                    '123': {'missing': True}
                }
            }
        }
        
        result = self.service.get_translation('nonexistentword', 'NOUN')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Translation failed: Word not found in Wiktionary')
        self.assertEqual(result['translations'], [])
    
    @patch('translation.TranslationService._make_request')
    def test_get_translation_success(self, mock_request):
        """Test successful translation."""
        mock_request.return_value = {
            'query': {
                'pages': {
                    '123': {
                        'revisions': [{
                            'slots': {
                                'main': {
                                    '*': '''
                                    ==German==
                                    ===Noun===
                                    # house
                                    # building
                                    '''
                                }
                            }
                        }]
                    }
                }
            }
        }
        
        result = self.service.get_translation('haus', 'NOUN')
        
        self.assertTrue(result['success'])
        self.assertIsNone(result['error'])
        self.assertIn('house', result['translations'])
        self.assertEqual(result['lemma'], 'haus')
        self.assertEqual(result['pos'], 'NOUN')
    
    @patch('translation.TranslationService.get_translation')
    @patch('translation.time.sleep')
    def test_get_batch_translations(self, mock_sleep, mock_get_translation):
        """Test batch translation functionality."""
        # Mock individual translation results
        mock_get_translation.side_effect = [
            {'success': True, 'translations': ['house'], 'lemma': 'haus', 'pos': 'NOUN'},
            {'success': False, 'error': 'Not found', 'translations': [], 'lemma': 'xyz', 'pos': 'VERB'}
        ]
        
        word_list = [('haus', 'NOUN'), ('xyz', 'VERB')]
        results = self.service.get_batch_translations(word_list)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]['success'])
        self.assertFalse(results[1]['success'])
        self.assertEqual(mock_get_translation.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleep after each request
    
    def test_get_batch_translations_empty_list(self):
        """Test batch translation with empty list."""
        results = self.service.get_batch_translations([])
        self.assertEqual(results, [])
    
    def test_format_translation_summary_success(self):
        """Test translation summary formatting for successful translation."""
        result = {
            'success': True,
            'lemma': 'haus',
            'pos': 'NOUN',
            'translations': ['house', 'building', 'home']
        }
        
        summary = self.service.format_translation_summary(result)
        expected = 'haus [NOUN]: house, building, home'
        self.assertEqual(summary, expected)
    
    def test_format_translation_summary_no_translations(self):
        """Test translation summary formatting with no translations."""
        result = {
            'success': True,
            'lemma': 'haus',
            'pos': 'NOUN',
            'translations': []
        }
        
        summary = self.service.format_translation_summary(result)
        expected = 'haus [NOUN]: (no translations found)'
        self.assertEqual(summary, expected)
    
    def test_format_translation_summary_failure(self):
        """Test translation summary formatting for failed translation."""
        result = {
            'success': False,
            'lemma': 'xyz',
            'error': 'API error'
        }
        
        summary = self.service.format_translation_summary(result)
        expected = 'xyz: API error'
        self.assertEqual(summary, expected)


class TestConvenienceFunctions(unittest.TestCase):
    """Test cases for convenience functions."""
    
    @patch('translation.TranslationService')
    def test_translate_word(self, mock_service_class):
        """Test translate_word convenience function."""
        # Mock the service instance and its method
        mock_service = Mock()
        mock_service.get_translation.return_value = {'success': True, 'translations': ['house']}
        mock_service_class.return_value = mock_service
        
        result = translate_word('haus', 'NOUN')
        
        mock_service_class.assert_called_once()
        mock_service.get_translation.assert_called_once_with('haus', 'NOUN')
        self.assertEqual(result, {'success': True, 'translations': ['house']})
    
    @patch('translation.TranslationService')
    def test_translate_word_list(self, mock_service_class):
        """Test translate_word_list convenience function."""
        # Mock the service instance and its method
        mock_service = Mock()
        mock_service.get_batch_translations.return_value = [{'success': True}]
        mock_service_class.return_value = mock_service
        
        word_list = [('haus', 'NOUN')]
        result = translate_word_list(word_list)
        
        mock_service_class.assert_called_once()
        mock_service.get_batch_translations.assert_called_once_with(word_list)
        self.assertEqual(result, [{'success': True}])
    
    @patch('translation.translate_word')
    def test_get_best_translation_success(self, mock_translate):
        """Test get_best_translation with successful result."""
        mock_translate.return_value = {
            'success': True,
            'translations': ['house', 'building']
        }
        
        result = get_best_translation('haus', 'NOUN')
        
        self.assertEqual(result, 'house')
        mock_translate.assert_called_once_with('haus', 'NOUN')
    
    @patch('translation.translate_word')
    def test_get_best_translation_failure(self, mock_translate):
        """Test get_best_translation with failed result."""
        mock_translate.return_value = {
            'success': False,
            'translations': []
        }
        
        result = get_best_translation('xyz', 'NOUN')
        
        self.assertIsNone(result)
    
    @patch('translation.translate_word')
    def test_get_best_translation_empty_translations(self, mock_translate):
        """Test get_best_translation with empty translations list."""
        mock_translate.return_value = {
            'success': True,
            'translations': []
        }
        
        result = get_best_translation('xyz', 'NOUN')
        
        self.assertIsNone(result)


class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios."""
    
    def setUp(self):
        self.service = TranslationService()
    
    @patch('translation.requests.Session.get')
    def test_json_decode_error(self, mock_get):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service._make_request('http://test.com')
        self.assertIsNone(result)
    
    @patch('translation.requests.Session.get')
    def test_connection_error(self, mock_get):
        """Test handling of connection errors."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = self.service._make_request('http://test.com')
        self.assertIsNone(result)
    
    @patch('translation.TranslationService._make_request')
    def test_get_translation_no_query_data(self, mock_request):
        """Test translation when API returns no query data."""
        mock_request.return_value = {'other': 'data'}
        
        result = self.service.get_translation('test', 'NOUN')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Translation failed: No page data found')
    
    @patch('translation.TranslationService._make_request')
    def test_get_translation_no_revisions(self, mock_request):
        """Test translation when page has no revisions."""
        mock_request.return_value = {
            'query': {
                'pages': {
                    '123': {'revisions': []}
                }
            }
        }
        
        result = self.service.get_translation('test', 'NOUN')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Translation failed: No content available')


if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)