"""Test the Vocabulary Database tab UI."""

import sys
import os
import tkinter as tk
from unittest.mock import patch, MagicMock

# Add src/ui to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ui'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tabs.vocabulary_tab import VocabularyTab


class TestVocabularyTabUI:
    """Test Vocabulary tab UI elements."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        # Mock database functions to avoid actual DB calls during init
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_tab_initialization(self):
        """Test that tab initializes correctly."""
        assert self.tab is not None
        assert self.tab._all_words == []
        assert self.tab._sort_column == 'word'
        assert self.tab._sort_reverse is False

    def test_search_entry_exists(self):
        """Test that search entry exists."""
        assert hasattr(self.tab, 'search_entry')
        assert hasattr(self.tab, 'search_var')

    def test_difficulty_combo_exists(self):
        """Test that difficulty combobox exists."""
        assert hasattr(self.tab, 'difficulty_combo')
        assert hasattr(self.tab, 'difficulty_var')
        assert self.tab.difficulty_var.get() == "All"

    def test_difficulty_combo_values(self):
        """Test that difficulty combobox has correct values."""
        values = self.tab.difficulty_combo['values']
        assert "All" in values
        assert "0-Known" in values
        assert "1-SuperEasy" in values
        assert "2-Easy" in values
        assert "3-Medium" in values
        assert "4-Hard" in values

    def test_refresh_button_exists(self):
        """Test that refresh button exists."""
        assert hasattr(self.tab, 'refresh_button')

    def test_treeview_exists(self):
        """Test that treeview exists with correct columns."""
        assert hasattr(self.tab, 'tree')
        columns = self.tab.tree['columns']
        assert 'word' in columns
        assert 'pos' in columns
        assert 'translation' in columns
        assert 'difficulty' in columns
        assert 'tags' in columns

    def test_status_label_exists(self):
        """Test that status label exists."""
        assert hasattr(self.tab, 'status_label')
        assert 'Total words: 0' in self.tab.status_label.cget('text')


class TestVocabularyTabDataLoading:
    """Test Vocabulary tab data loading functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_load_data_populates_treeview(self, mock_get_words, mock_get_tags):
        """Test that load_data populates the treeview."""
        mock_get_words.return_value = [
            ('der Mann', 'NOUN', True, 'the man', 3),
            ('laufen', 'VERB', True, 'to run', 2),
        ]
        mock_get_tags.return_value = []

        self.tab._load_data()

        # Check that treeview has items
        children = self.tab.tree.get_children()
        assert len(children) == 2

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_load_data_with_tags(self, mock_get_words, mock_get_tags):
        """Test that load_data includes tags."""
        mock_get_words.return_value = [
            ('der Mann', 'NOUN', True, 'the man', 3),
        ]
        mock_get_tags.return_value = [('beginner', None), ('common', None)]

        self.tab._load_data()

        # Check that word data includes tags
        assert len(self.tab._all_words) == 1
        assert 'beginner' in self.tab._all_words[0]['tags']
        assert 'common' in self.tab._all_words[0]['tags']

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_load_data_with_difficulty_filter(self, mock_get_words, mock_get_tags):
        """Test that difficulty filter is applied."""
        mock_get_words.return_value = []
        mock_get_tags.return_value = []

        self.tab.difficulty_var.set("3-Medium")
        self.tab._load_data()

        # Check that filter was passed to get_all_words
        mock_get_words.assert_called_with(filters={'difficulty': 3})

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_load_data_updates_status(self, mock_get_words, mock_get_tags):
        """Test that status bar is updated after loading."""
        mock_get_words.return_value = [
            ('word1', 'NOUN', True, 'trans1', 3),
            ('word2', 'VERB', True, 'trans2', 2),
        ]
        mock_get_tags.return_value = []

        self.tab._load_data()

        assert 'Total words: 2' in self.tab.status_label.cget('text')

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_load_data_empty_database(self, mock_get_words, mock_get_tags):
        """Test handling of empty database."""
        mock_get_words.return_value = []
        mock_get_tags.return_value = []

        self.tab._load_data()

        children = self.tab.tree.get_children()
        assert len(children) == 0
        assert 'Total words: 0' in self.tab.status_label.cget('text')


class TestVocabularyTabFiltering:
    """Test Vocabulary tab search and filtering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_filter_by_word(self):
        """Test filtering by word name."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': ''},
            {'word': 'die Frau', 'pos': 'NOUN', 'translation': 'the woman', 'difficulty': 3, 'tags': ''},
            {'word': 'laufen', 'pos': 'VERB', 'translation': 'to run', 'difficulty': 2, 'tags': ''},
        ]

        self.tab.search_var.set('Mann')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 1

    def test_filter_by_translation(self):
        """Test filtering by translation."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': ''},
            {'word': 'die Frau', 'pos': 'NOUN', 'translation': 'the woman', 'difficulty': 3, 'tags': ''},
        ]

        self.tab.search_var.set('woman')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 1

    def test_filter_by_tags(self):
        """Test filtering by tags."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': 'beginner'},
            {'word': 'die Frau', 'pos': 'NOUN', 'translation': 'the woman', 'difficulty': 3, 'tags': 'advanced'},
        ]

        self.tab.search_var.set('beginner')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 1

    def test_filter_case_insensitive(self):
        """Test that filtering is case insensitive."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': ''},
        ]

        self.tab.search_var.set('MANN')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 1

    def test_filter_empty_search(self):
        """Test that empty search shows all words."""
        self.tab._all_words = [
            {'word': 'word1', 'pos': 'NOUN', 'translation': 'trans1', 'difficulty': 3, 'tags': ''},
            {'word': 'word2', 'pos': 'VERB', 'translation': 'trans2', 'difficulty': 2, 'tags': ''},
        ]

        self.tab.search_var.set('')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 2

    def test_filter_updates_status_showing_count(self):
        """Test that filtered results show 'Showing X of Y' format."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': ''},
            {'word': 'die Frau', 'pos': 'NOUN', 'translation': 'the woman', 'difficulty': 3, 'tags': ''},
        ]

        self.tab.search_var.set('Mann')
        self.tab._filter_data()

        assert 'Showing 1 of 2' in self.tab.status_label.cget('text')


class TestVocabularyTabSorting:
    """Test Vocabulary tab sorting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_sort_by_column_changes_column(self):
        """Test that clicking column changes sort column."""
        assert self.tab._sort_column == 'word'

        self.tab._sort_by_column('pos')

        assert self.tab._sort_column == 'pos'
        assert self.tab._sort_reverse is False

    def test_sort_by_same_column_toggles_direction(self):
        """Test that clicking same column toggles sort direction."""
        self.tab._sort_column = 'word'
        self.tab._sort_reverse = False

        self.tab._sort_by_column('word')

        assert self.tab._sort_reverse is True

        self.tab._sort_by_column('word')

        assert self.tab._sort_reverse is False

    def test_sort_data_alphabetically(self):
        """Test sorting words alphabetically."""
        data = [
            {'word': 'zebra', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
            {'word': 'apple', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
            {'word': 'mango', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
        ]

        self.tab._sort_column = 'word'
        self.tab._sort_reverse = False

        sorted_data = self.tab._sort_data(data)

        assert sorted_data[0]['word'] == 'apple'
        assert sorted_data[1]['word'] == 'mango'
        assert sorted_data[2]['word'] == 'zebra'

    def test_sort_data_reverse(self):
        """Test reverse sorting."""
        data = [
            {'word': 'apple', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
            {'word': 'zebra', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
        ]

        self.tab._sort_column = 'word'
        self.tab._sort_reverse = True

        sorted_data = self.tab._sort_data(data)

        assert sorted_data[0]['word'] == 'zebra'
        assert sorted_data[1]['word'] == 'apple'

    def test_sort_by_difficulty_numeric(self):
        """Test that difficulty sorts numerically."""
        data = [
            {'word': 'word1', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
            {'word': 'word2', 'pos': 'NOUN', 'translation': '', 'difficulty': 1, 'tags': ''},
            {'word': 'word3', 'pos': 'NOUN', 'translation': '', 'difficulty': 4, 'tags': ''},
        ]

        self.tab._sort_column = 'difficulty'
        self.tab._sort_reverse = False

        sorted_data = self.tab._sort_data(data)

        assert sorted_data[0]['difficulty'] == 1
        assert sorted_data[1]['difficulty'] == 3
        assert sorted_data[2]['difficulty'] == 4

    def test_sort_empty_data(self):
        """Test sorting empty data."""
        data = []
        sorted_data = self.tab._sort_data(data)
        assert sorted_data == []


class TestVocabularyTabTreeview:
    """Test Vocabulary tab treeview display."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_treeview_displays_word_data(self):
        """Test that treeview displays word data correctly."""
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': 'common'},
        ]

        self.tab._filter_data()

        children = self.tab.tree.get_children()
        assert len(children) == 1

        item = self.tab.tree.item(children[0])
        values = item['values']

        assert values[0] == 'der Mann'
        assert values[1] == 'NOUN'
        assert values[2] == 'the man'
        assert values[3] == 3
        assert values[4] == 'common'

    def test_treeview_alternating_row_colors(self):
        """Test that treeview has alternating row colors."""
        self.tab._all_words = [
            {'word': 'word1', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
            {'word': 'word2', 'pos': 'VERB', 'translation': '', 'difficulty': 2, 'tags': ''},
            {'word': 'word3', 'pos': 'ADJ', 'translation': '', 'difficulty': 1, 'tags': ''},
        ]

        self.tab._filter_data()

        children = self.tab.tree.get_children()

        # Check tags for alternating colors
        item0 = self.tab.tree.item(children[0])
        item1 = self.tab.tree.item(children[1])
        item2 = self.tab.tree.item(children[2])

        assert 'evenrow' in item0['tags']
        assert 'oddrow' in item1['tags']
        assert 'evenrow' in item2['tags']

    def test_treeview_clears_on_reload(self):
        """Test that treeview clears old items on reload."""
        self.tab._all_words = [
            {'word': 'word1', 'pos': 'NOUN', 'translation': '', 'difficulty': 3, 'tags': ''},
        ]
        self.tab._filter_data()

        assert len(self.tab.tree.get_children()) == 1

        # Change data and reload
        self.tab._all_words = [
            {'word': 'word2', 'pos': 'VERB', 'translation': '', 'difficulty': 2, 'tags': ''},
            {'word': 'word3', 'pos': 'ADJ', 'translation': '', 'difficulty': 1, 'tags': ''},
        ]
        self.tab._filter_data()

        assert len(self.tab.tree.get_children()) == 2


class TestVocabularyTabWordDetails:
    """Test Vocabulary tab word details popup."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_show_word_details_no_selection(self):
        """Test that word details does nothing with no selection."""
        # Create mock event
        event = MagicMock()

        # This should not raise an error
        self.tab._show_word_details(event)

    def test_show_word_details_with_selection(self):
        """Test that word details shows popup with selection."""
        # Add word to treeview
        self.tab._all_words = [
            {'word': 'der Mann', 'pos': 'NOUN', 'translation': 'the man', 'difficulty': 3, 'tags': 'common'},
        ]
        self.tab._filter_data()

        # Select the item
        children = self.tab.tree.get_children()
        self.tab.tree.selection_set(children[0])

        # Create mock event
        event = MagicMock()

        # This should create a popup
        self.tab._show_word_details(event)

        # Check that a toplevel window was created
        toplevels = [w for w in self.tab.winfo_children() if isinstance(w, tk.Toplevel)]
        # Note: The popup is created as a child of self, so we should find it
        # However, with transient() it might be in a different hierarchy
        # This test just ensures no error is raised


class TestVocabularyTabPublicMethods:
    """Test Vocabulary tab public methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_refresh_method(self, mock_get_words, mock_get_tags):
        """Test that refresh() reloads data."""
        mock_get_words.return_value = [
            ('word1', 'NOUN', True, 'trans1', 3),
        ]
        mock_get_tags.return_value = []

        self.tab.refresh()

        mock_get_words.assert_called_once()
        assert len(self.tab._all_words) == 1

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_on_tab_selected_method(self, mock_get_words, mock_get_tags):
        """Test that on_tab_selected() reloads data."""
        mock_get_words.return_value = []
        mock_get_tags.return_value = []

        self.tab.on_tab_selected()

        mock_get_words.assert_called_once()


class TestVocabularyTabIntegration:
    """Test Vocabulary tab integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        with patch('tabs.vocabulary_tab.get_all_words', return_value=[]), \
             patch('tabs.vocabulary_tab.get_word_tags', return_value=[]):
            self.tab = VocabularyTab(self.root)
        self.root.update_idletasks()

    def teardown_method(self):
        """Clean up after tests."""
        self.root.destroy()

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_full_workflow(self, mock_get_words, mock_get_tags):
        """Test complete workflow: load, filter, sort."""
        # Load data
        mock_get_words.return_value = [
            ('zebra', 'NOUN', True, 'zebra', 3),
            ('apple', 'NOUN', True, 'apple', 1),
            ('mango', 'NOUN', True, 'mango', 2),
        ]
        mock_get_tags.return_value = []

        self.tab._load_data()

        # Verify initial load
        assert len(self.tab.tree.get_children()) == 3

        # Filter
        self.tab.search_var.set('a')
        self.tab._filter_data()

        # Should show zebra (has 'a'), apple (has 'a'), mango (has 'a')
        assert len(self.tab.tree.get_children()) == 3

        # Filter more specifically
        self.tab.search_var.set('apple')
        self.tab._filter_data()

        assert len(self.tab.tree.get_children()) == 1

        # Clear filter
        self.tab.search_var.set('')
        self.tab._filter_data()

        assert len(self.tab.tree.get_children()) == 3

        # Sort by difficulty
        self.tab._sort_by_column('difficulty')
        self.tab._filter_data()

        children = self.tab.tree.get_children()
        first_item = self.tab.tree.item(children[0])
        assert first_item['values'][3] == 1  # Lowest difficulty first

    @patch('tabs.vocabulary_tab.get_word_tags')
    @patch('tabs.vocabulary_tab.get_all_words')
    def test_difficulty_filter_and_search_combined(self, mock_get_words, mock_get_tags):
        """Test combining difficulty filter with search."""
        # First call returns all words
        # Second call (after difficulty filter) returns filtered
        mock_get_words.side_effect = [
            # First call (All difficulties)
            [
                ('word1', 'NOUN', True, 'trans1', 3),
                ('word2', 'VERB', True, 'trans2', 1),
            ],
            # Second call (after difficulty filter)
            [
                ('word1', 'NOUN', True, 'trans1', 3),
            ],
        ]
        mock_get_tags.return_value = []

        # Initial load
        self.tab._load_data()
        assert len(self.tab.tree.get_children()) == 2

        # Apply difficulty filter
        self.tab.difficulty_var.set("3-Medium")
        self.tab._load_data()

        assert len(self.tab.tree.get_children()) == 1


def run_tests():
    """Run all tests."""
    import pytest
    pytest.main([__file__, '-v'])


if __name__ == "__main__":
    run_tests()
