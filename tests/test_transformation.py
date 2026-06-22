
import os
import sys
import tempfile
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
import transformation_iterative as ti
import transformation_normal as tn

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

    def test_iterative_question_variation_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Scheduled date': pd.NA, 'Input date': '2025-01-02'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-02', 'Question': 'Q1?', 'Answer Text': pd.NA, 'Answer Value': 'B'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Q1_1', result.columns)
            self.assertIn('Q1_2', result.columns)
            self.assertNotIn('Q1?_1', result.columns)
            self.assertNotIn('Q1?_2', result.columns)

    def test_question_colon_spacing_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Finale Vorbereitung', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Finale Vorbereitung', 'Entry Date': '2025-01-01', 'Question': 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben: Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen', 'Answer Text': pd.NA, 'Answer Value': 'Ja'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Finale Vorbereitung', 'Entry Date': '2025-01-01', 'Question': 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben:Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen', 'Answer Text': pd.NA, 'Answer Value': 'Nein'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            normalized_col = 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben: Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen_1'
            raw_col = 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben:Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen_1'
            self.assertIn(normalized_col, result.columns)
            self.assertNotIn(raw_col, result.columns)

    def test_iterative_preserves_rows_with_no_answers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'A', 'Content Name': 'C1', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 2, 'Pathway Name': 'B', 'Content Name': 'C2', 'Scheduled date': pd.NA, 'Input date': '2025-01-02'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'A', 'Content Name': 'C1', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertEqual(result.shape[0], 2)
            self.assertIn('B', result['Pathway Name'].values)

    def test_timestamp_tolerance_assigns_nearby_answers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Scheduled date': pd.NA, 'Input date': '2025-01-01 10:00:00'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Allgemeine Gesundheit', 'Entry Date': '2025-01-01 10:00:01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Q1_1', result.columns)
            self.assertEqual(result.loc[0, 'Q1_1'], 'A')

    def test_weekly_movement_diary_is_iterative(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Wöchentliches Bewegungstagebuch', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Wöchentliches Bewegungstagebuch', 'Scheduled date': pd.NA, 'Input date': '2025-01-08'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Wöchentliches Bewegungstagebuch', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Wöchentliches Bewegungstagebuch', 'Entry Date': '2025-01-08', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'B'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Q1_1', result.columns)
            self.assertIn('Q1_2', result.columns)
            self.assertEqual(result.loc[0, 'Q1_1'], 'A')
            self.assertEqual(result.loc[0, 'Q1_2'], 'B')

    def test_normal_question_variation_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'NonIterative', 'Entry Date': '2025-01-01', 'Question': 'Q1?', 'Answer Text': pd.NA, 'Answer Value': 'B'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = tn.process_normal_files(content_path, answers_path)

            self.assertIn('Q1', result.columns)
            self.assertNotIn('Q1?', result.columns)

    def test_normal_preserves_rows_with_no_answers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'A', 'Content Name': 'C1', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 2, 'Pathway Name': 'B', 'Content Name': 'C2', 'Scheduled date': pd.NA, 'Input date': '2025-01-02'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'A', 'Content Name': 'C1', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = tn.process_normal_files(content_path, answers_path)

            self.assertEqual(result.shape[0], 2)
            self.assertIn('B', result['Pathway Name'].values)

if __name__ == '__main__':
    unittest.main()
