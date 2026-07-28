
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
    def test_repeated_questionnaire_submissions_are_preserved_as_occurrences(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-01', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-02', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'B'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-03', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'C'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Daily Diary_1_Mood', result.columns)
            self.assertIn('Daily Diary_2_Mood', result.columns)
            self.assertIn('Daily Diary_3_Mood', result.columns)
            self.assertEqual(result.loc[0, 'Daily Diary_1_Mood'], 'A')
            self.assertEqual(result.loc[0, 'Daily Diary_2_Mood'], 'B')
            self.assertEqual(result.loc[0, 'Daily Diary_3_Mood'], 'C')

            validation_report = result.attrs.get('questionnaire_occurrence_validation')
            self.assertEqual(validation_report['total_questionnaire_submissions_source'], 3)
            self.assertEqual(validation_report['total_questionnaire_occurrences_output'], 3)
            self.assertEqual(validation_report['mismatches'], [])

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

            self.assertIn('NonIterative_1_Q1', result.columns)
            self.assertIn('NonIterative_2_Q1', result.columns)
            self.assertIn('Allgemeine Gesundheit_1_Q2', result.columns)
            self.assertIn('Allgemeine Gesundheit_2_Q2', result.columns)
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

            self.assertIn('NonIterative_1_Q1', result.columns)
            self.assertIn('NonIterative_2_Q1', result.columns)
            self.assertNotIn('NonIterative_1_Q1?', result.columns)
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

            normalized_col = 'Finale Vorbereitung_1_Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben: Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen'
            raw_col = 'Finale Vorbereitung_1_Wenn Sie kohlenhydrathaltige Drinks im Rahmen der Sprechstunde von uns erhalten haben:Haben Sie die kohlenhydrathaltigen Drinks wie geplant zu sich genommen'
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
            # Three separate scheduled BMI submissions (one per week). Each entry
            # date is its own submission event, so occurrence numbers must track
            # the entry date — not the individual question — even though only one
            # question happens to be answered on each date.
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-01', 'Question': 'BMI', 'Answer Text': pd.NA, 'Answer Value': '20'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-08', 'Question': 'Gewicht', 'Answer Text': pd.NA, 'Answer Value': '70'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'BMI', 'Entry Date': '2025-01-15', 'Question': 'Größe (in Zentimetern)', 'Answer Text': pd.NA, 'Answer Value': '175'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('BMI_1_BMI', result.columns)
            self.assertIn('BMI_2_Gewicht', result.columns)
            self.assertIn('BMI_3_Größe (in Zentimetern)', result.columns)
            self.assertEqual(result.loc[0, 'BMI_1_BMI'], 20)
            self.assertEqual(result.loc[0, 'BMI_2_Gewicht'], 70)
            self.assertEqual(result.loc[0, 'BMI_3_Größe (in Zentimetern)'], 175)

    def test_repeated_multi_question_submissions_share_occurrence_across_questions(self):
        """A submission event (same Entry Date) must assign the SAME occurrence
        number to every question it contains, even if some questions are only
        present on some occasions. This is what the questionnaire_occurrence_validation
        report relies on to correctly count submissions vs. answer rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Entry Date': '2025-01-01', 'Question': 'Pain level', 'Answer Text': pd.NA, 'Answer Value': 'P1'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Entry Date': '2025-01-01', 'Question': 'Pain location', 'Answer Text': pd.NA, 'Answer Value': 'L1'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Entry Date': '2025-01-02', 'Question': 'Pain level', 'Answer Text': pd.NA, 'Answer Value': 'P2'},
                # 'Pain location' skipped on 2025-01-02 — should not shift its own occurrence numbering out of sync
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Entry Date': '2025-01-03', 'Question': 'Pain level', 'Answer Text': pd.NA, 'Answer Value': 'P3'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Schmerztagebuch', 'Entry Date': '2025-01-03', 'Question': 'Pain location', 'Answer Text': pd.NA, 'Answer Value': 'L3'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertEqual(result.loc[0, 'Schmerztagebuch_1_Pain level'], 'P1')
            self.assertEqual(result.loc[0, 'Schmerztagebuch_1_Pain location'], 'L1')
            self.assertEqual(result.loc[0, 'Schmerztagebuch_2_Pain level'], 'P2')
            self.assertEqual(result.loc[0, 'Schmerztagebuch_3_Pain level'], 'P3')
            self.assertEqual(result.loc[0, 'Schmerztagebuch_3_Pain location'], 'L3')
            self.assertNotIn('Schmerztagebuch_2_Pain location', result.columns)

            validation_report = result.attrs.get('questionnaire_occurrence_validation')
            self.assertEqual(validation_report['total_questionnaire_submissions_source'], 3)
            self.assertEqual(validation_report['total_questionnaire_occurrences_output'], 3)
            self.assertEqual(validation_report['mismatches'], [])

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

            self.assertIn('Allgemeine Gesundheit_1_Q1', result.columns)
            self.assertEqual(result.loc[0, 'Allgemeine Gesundheit_1_Q1'], 'A')

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

            self.assertIn('Wöchentliches Bewegungstagebuch_1_Q1', result.columns)
            self.assertIn('Wöchentliches Bewegungstagebuch_2_Q1', result.columns)
            self.assertEqual(result.loc[0, 'Wöchentliches Bewegungstagebuch_1_Q1'], 'A')
            self.assertEqual(result.loc[0, 'Wöchentliches Bewegungstagebuch_2_Q1'], 'B')

    def test_custom_iterative_content_name_can_be_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'My Custom Diary', 'Scheduled date': pd.NA, 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'My Custom Diary', 'Scheduled date': pd.NA, 'Input date': '2025-01-08'},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'My Custom Diary', 'Entry Date': '2025-01-01', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'My Custom Diary', 'Entry Date': '2025-01-08', 'Question': 'Q1', 'Answer Text': pd.NA, 'Answer Value': 'B'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(
                content_path,
                answers_path,
                iterative_content_names=['custom diary'],
            )

            self.assertIn('My Custom Diary_1_Q1', result.columns)
            self.assertIn('My Custom Diary_2_Q1', result.columns)
            self.assertEqual(result.loc[0, 'My Custom Diary_1_Q1'], 'A')
            self.assertEqual(result.loc[0, 'My Custom Diary_2_Q1'], 'B')

    def test_iterative_adds_scheduled_date_per_occurrence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, 'content.csv')
            answers_path = os.path.join(tmpdir, 'answers.csv')

            # The schedule/content file logs "Input date" once a scheduled item
            # is actually submitted — the same timestamp that shows up as
            # "Entry Date" in the Answers file. That shared timestamp is what
            # ties a "Scheduled date" to a specific occurrence.
            content = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Scheduled date': '2025-01-01', 'Input date': '2025-01-01'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Scheduled date': '2025-01-07', 'Input date': '2025-01-02'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Scheduled date': '2025-01-14', 'Input date': pd.NA},
            ])
            answers = pd.DataFrame([
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-01', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'A'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-02', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'B'},
                {'Patient ID': 1, 'Pathway Name': 'P', 'Content Name': 'Daily Diary', 'Entry Date': '2025-01-03', 'Question': 'Mood', 'Answer Text': pd.NA, 'Answer Value': 'C'},
            ])

            content.to_csv(content_path, index=False)
            answers.to_csv(answers_path, index=False)

            result = ti.process_iterative_files(content_path, answers_path)

            self.assertIn('Daily Diary_1_Date', result.columns)
            self.assertIn('Daily Diary_2_Date', result.columns)
            self.assertIn('Daily Diary_3_Date', result.columns)
            self.assertEqual(pd.Timestamp(result.loc[0, 'Daily Diary_1_Date']), pd.Timestamp('2025-01-01'))
            self.assertEqual(pd.Timestamp(result.loc[0, 'Daily Diary_2_Date']), pd.Timestamp('2025-01-07'))
            # Occurrence 3 (2025-01-03) has no matching schedule row, so its date is blank
            self.assertTrue(pd.isna(result.loc[0, 'Daily Diary_3_Date']))

            # Answers must still be fully preserved alongside the new date columns
            self.assertEqual(result.loc[0, 'Daily Diary_1_Mood'], 'A')
            self.assertEqual(result.loc[0, 'Daily Diary_2_Mood'], 'B')
            self.assertEqual(result.loc[0, 'Daily Diary_3_Mood'], 'C')
            validation_report = result.attrs.get('questionnaire_occurrence_validation')
            self.assertEqual(validation_report['mismatches'], [])

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

            self.assertIn('NonIterative_Q1', result.columns)
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
