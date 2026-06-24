
import os
import sys
import tempfile
import unittest
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))
import transformation_common as tc
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

            self.assertIn('Q1_NonIterative', result.columns)
            self.assertNotIn('Q1_NonIterative_1', result.columns)
            self.assertNotIn('Q1_NonIterative_2', result.columns)
            self.assertNotIn('Q1?', result.columns)

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

            normalized_col = 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben: Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen_Finale Vorbereitung'
            raw_col = 'Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben:Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen_Finale Vorbereitung'
            self.assertIn(normalized_col, result.columns)
            self.assertNotIn(raw_col, result.columns)

    def test_bmi_iterative_question_creates_three_iterations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Scheduled date': pd.NA, 'Input date': '2025-01-08'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Scheduled date': pd.NA, 'Input date': '2025-01-15'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-01', 'Question': 'BMI', 'Answer Text': pd.NA, 'Answer Value': '20'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-08', 'Question': 'Gewicht', 'Answer Text': pd.NA, 'Answer Value': '70'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-15', 'Question': 'Größe (in Zentimetern)', 'Answer Text': pd.NA, 'Answer Value': '175'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('BMI_BMI_1', result.columns)
            self.assertIn('Gewicht_BMI_1', result.columns)
            self.assertIn('Größe (in Zentimetern)_BMI_1', result.columns)
            self.assertEqual(result.loc[0, 'BMI_BMI_1'], '20')
            self.assertEqual(result.loc[0, 'Gewicht_BMI_1'], '70')
            self.assertEqual(result.loc[0, 'Größe (in Zentimetern)_BMI_1'], '175')

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

            self.assertIn('Q1_Allgemeine Gesundheit_1', result.columns)
            self.assertEqual(result.loc[0, 'Q1_Allgemeine Gesundheit_1'], 'A')

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

            self.assertIn('Q1_Wöchentliches Bewegungstagebuch_1', result.columns)
            self.assertIn('Q1_Wöchentliches Bewegungstagebuch_2', result.columns)
            self.assertEqual(result.loc[0, 'Q1_Wöchentliches Bewegungstagebuch_1'], 'A')
            self.assertEqual(result.loc[0, 'Q1_Wöchentliches Bewegungstagebuch_2'], 'B')

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

    def test_read_input_file_reads_xlsx_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, 'content.xlsx')
            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'C1', 'Input date': '2025-01-01'},
            ])
            content.to_excel(file_path, index=False)

            read_df = tc.read_input_file(file_path)
            self.assertListEqual(list(read_df.columns), list(content.columns))
            self.assertEqual(read_df.loc[0, 'Patient ID'], 1)

    def test_read_input_file_detects_shifted_excel_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, 'content_shifted.xlsx')
            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'C1', 'Input date': '2025-01-01'},
            ])

            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                pd.DataFrame([['', '', '', ''], ['', '', '', '']]).to_excel(writer, header=False, index=False)
                content.to_excel(writer, index=False, startrow=2)

            read_df = tc.read_input_file(file_path)
            self.assertListEqual(list(read_df.columns), list(content.columns))
            self.assertEqual(read_df.loc[0, 'Patient ID'], 1)

    def test_prepare_endpoint_file_converts_entlassung_1_0_to_ja(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            endpoint_path = os.path.join(tmpdir, 'endpoints.csv')
            endpoints = pd.DataFrame([
                {
                    'Patient ID': 1,
                    'Pathway Name': 'P',
                    'Entlassung Exitus': 1.0,
                    'Entlassung Nachhause': 0.0,
                    'Entlassung Pflegeheim': '1.0',
                    'Entlassung AHB Reha': '0.0',
                }
            ])
            endpoints.to_csv(endpoint_path, index=False)

            prepared = tc.prepare_endpoint_file(endpoint_path)

            self.assertEqual(prepared.loc[0, 'Endpoint_Entlassung Exitus'], 'Ja')
            self.assertTrue(pd.isna(prepared.loc[0, 'Endpoint_Entlassung Nachhause']))
            self.assertEqual(prepared.loc[0, 'Endpoint_Entlassung Pflegeheim'], 'Ja')
            self.assertTrue(pd.isna(prepared.loc[0, 'Endpoint_Entlassung AHB Reha']))

if __name__ == '__main__':
    unittest.main()
