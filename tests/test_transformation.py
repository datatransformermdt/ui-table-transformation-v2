
import os
import sys
import tempfile
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
import transformation_iterative as ti

class TransformationIterativeTest(unittest.TestCase):
    def test_non_iterative_questionnaire_collapses_to_single_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Scheduled date': pd.NA, 'Input date': '2025-01-02'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Scheduled date': pd.NA, 'Input date': '2025-01-02'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-02', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'B'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Entry Date': '2025-01-01', 'Question': 'Q2', 'Answer Text': pd.NA, 'Answer Value': 'X'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Entry Date': '2025-01-02', 'Question': 'Q2', 'Answer Text': pd.NA, 'Answer Value': 'Y'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Q1_NonIterative', result.columns)
            self.assertNotIn('Q1_NonIterative_1', result.columns)
            self.assertIn('Q2_Allgemeine Gesundheit_1', result.columns)
            self.assertIn('Q2_Allgemeine Gesundheit_2', result.columns)
            self.assertEqual(result.shape[0], 1)

if __name__ == '__main__':
    unittest.main()
