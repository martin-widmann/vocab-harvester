#!/usr/bin/env python3
"""
VocabHarvest - Main entry point for text processing pipeline
"""

from parser import process_text_input

def main():
    """Main function to demonstrate text input processing."""
    print("VocabHarvest - Text Processing Pipeline")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Process text input")
        print("2. Exit")
        
        choice = input("\nSelect option (1-2): ").strip()
        
        if choice == "1":
            print("\nEnter text to process (press Enter twice when done):")
            lines = []
            while True:
                line = input()
                if line == "":
                    if lines:  # If we have content, stop
                        break
                    else:  # If no content yet, continue
                        continue
                lines.append(line)
            
            text = "\n".join(lines)
            
            if text.strip():
                print(f"\nProcessing text: {text[:50]}...")
                process_text_input(text)
            else:
                print("No text entered.")
                
        elif choice == "2":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please choose 1 or 2.")

if __name__ == "__main__":
    main()