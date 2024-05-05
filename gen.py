import os
from flask import Flask, render_template, request
import re
from pdfminer.high_level import extract_text
import docx2txt
import pymysql
import google.generativeai as genai

app = Flask(__name__)

# Set the Google API key
os.environ['GOOGLE_API_KEY'] = "AIzaSyCThNAz1WfOr3zWwdD3Bo3YhlgDYa9SMms"

# Configure the generative AI module with the API key
genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

# Initialize the GenerativeModel with the desired model (e.g., "gemini-pro")
model = genai.GenerativeModel('gemini-pro')

# MySQL connection configuration
mysql_host = 'localhost'
mysql_user = 'root'
mysql_password = '7781'
mysql_database = 'RESUME'

# Connect to MySQL
db_connection = pymysql.connect(
    host=mysql_host,
    user=mysql_user,
    password=mysql_password,
    database=mysql_database
)
db_cursor = db_connection.cursor()

# Create table if not exists
db_cursor.execute("""
    CREATE TABLE IF NOT EXISTS resume (
        id INT AUTO_INCREMENT PRIMARY KEY,
        skills TEXT,
        file_name VARCHAR(255),
        file LONGBLOB
    )
""")

def extract_text_from_pdf(pdf_path):
    return extract_text(pdf_path)

def extract_text_from_docx(docx_path):
    return docx2txt.process(docx_path)

def extract_skills_from_resume(text, skills_list):
    skills = []
    for skill in skills_list:
        pattern = r"\b{}\b".format(re.escape(skill))
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            skills.append(skill)
    return skills

def remove_keywords(text, keywords):
    for keyword in keywords:
        text = text.replace(keyword, '')
    return text.strip()  # Remove leading and trailing spaces


def remove_unwanted_elements(options):
    # Create a list of all 26 alphabets in lowercase and uppercase
    alphabets = [chr(i) for i in range(ord('a'), ord('z')+1)] + [chr(i) for i in range(ord('A'), ord('Z')+1)]

    # Create the keywords in the specified formats
    keywords = ["**Options:**", "**Explanation:**", " **Correct Answer:**", " **Option 1:**", " **Option 2:**", " **option4:** ", " **Option 5:**", "*", "**", "**Correct Answer:** ", " Option 1:", " Option 2:", " Option 4:", " Option 5:", "Answer Options:", "```","Question: ", "Questions: ","Question","Questions","Multiple Choice Options:","Multiple Choice Options", "A.A", "B.B", "C.C", "D.D", "A.A.", "B.B.", "C.C.", "D.D.", "Answer: ","Answers: "]+ \
                [f"**Option {alpha}:**" for alpha in alphabets] + \
                [f"**Question:**", "(a)", "(A)", "(b)", "(B)", "(c)", "(C)", "(d)", "(D)", "(e)", "(E)" ""] + \
                [f"**{alpha}.**" for alpha in alphabets] + \
                [f"**{alpha}.**," for alpha in alphabets] + \
                [f"**({alpha})**" for alpha in alphabets] + \
                [f"**,{alpha}" for alpha in alphabets] + \
                ["Option 1:", "Option 2:", "Option 3:", "Option 4:", "Option 1", "Option 2", "Option 3", "Option 4",
                 "Option A:", "Option B:", "Option C:", "Option D:", "Option A", "Option B", "Option C", "Option D",
                 "Option a:", "option b:", "option c:", "option d:", "option a", "option b", "option c", "option d",
                 "(a)", "(b)", "(c)", "(d)", "a)", "b)", "c)", "d)", "(A)", "(B)", "(C)", "(D)", "A).", "B)", "C)", "D)",
                 "Choice 1:", "Choice 2:", "Choice 3:", "Choice 4:", "Choice 1", "Choice 2", "Choice 3", "Choice 4",
                 "Choice A:", "Choice B:", "Choice C:", "Choice D:", "Choice A", "Choice B", "Choice C", "Choice D",
                 "Choice a:", "Choice b:", "Choice c:", "Choice d:", "Choice a", "Choice b", "Choice c", "Choice d",
                 "A. A.", "B. B.", "C. C.", "D. D."]

    cleaned_options = []
    for option in options:
        cleaned_option = remove_keywords(option, keywords)
        if cleaned_option:  # Check if the cleaned option is not an empty string
            cleaned_options.append(cleaned_option)
    return cleaned_options




def generate_questions_for_skills(skills_with_questions, question_mode, num_questions):
    generated_questions = []
    if question_mode == 'combined':
        total_skills = len(skills_with_questions)
        for skill, questions in skills_with_questions.items():
            # Calculate the proportion of questions for this skill
            skill_proportion = len(questions) / sum(len(questions) for questions in skills_with_questions.values())
            # Calculate the number of questions for this skill based on its proportion
            skill_num_questions = round(num_questions * skill_proportion)
            # Generate questions for this skill
            for _ in range(skill_num_questions):
                question_response = model.generate_content(f"Ask a question related to {skill}")
                options_response = model.generate_content(f"Generate multiple choice options for the question: {question_response.text}")
                processed_options = remove_unwanted_elements(options_response.text.split('\n'))  # Post-process the options
                # Label the options as A., B., C., and D.
                labeled_options = {f"{chr(65+i)}.": opt for i, opt in enumerate(processed_options)}
                generated_questions.append({
                    'question': question_response.text,
                    'options': labeled_options
                })
    else:  # separate
        for skill, questions in skills_with_questions.items():
            for _ in range(num_questions):
                question_response = model.generate_content(f"Ask a question related to {skill}")
                options_response = model.generate_content(f"Generate multiple choice options for the question: {question_response.text}")
                processed_options = remove_unwanted_elements(options_response.text.split('\n'))  # Post-process the options
                # Label the options as A., B., C., and D.
                labeled_options = {f"{chr(65+i)}.": opt for i, opt in enumerate(processed_options)}
                generated_questions.append({
                    'question': question_response.text,
                    'options': labeled_options
                })
    return generated_questions



@app.route('/')
def index():
    return render_template('res.html')

@app.route('/upload', methods=['POST'])
def extract_skills():
    if 'resume' not in request.files:
        return 'No file uploaded'

    resume_file = request.files['resume']
    if resume_file.filename == '':
        return 'No file selected'

    upload_dir = 'upload'
    os.makedirs(upload_dir, exist_ok=True)
    resume_path = os.path.join(upload_dir, resume_file.filename)
    resume_file.save(resume_path)

    if resume_path.endswith('.pdf'):
        text = extract_text_from_pdf(resume_path)
    elif resume_path.endswith('.docx'):
        text = extract_text_from_docx(resume_path)
    else:
        return 'Unsupported file format'

    skills_list = ['Python', 'Java', 'C', 'C++', 'SQL', 'MONGODB', 'Excel', 'Machine learning', 'R']

    extracted_skills = extract_skills_from_resume(text, skills_list)

    # Check if the document with the same filename already exists in the database
    db_cursor.execute("SELECT * FROM resume WHERE file_name = %s", (resume_file.filename,))
    existing_document = db_cursor.fetchone()

    if existing_document:
        return render_template('qns.html', skills=extracted_skills)
    else:
        with open(resume_path, 'rb') as file:
            resume_data = file.read()
        filename = os.path.basename(resume_path)
        skills_str = ','.join(extracted_skills)
        db_cursor.execute("INSERT INTO resume (skills, file_name, file) VALUES (%s, %s, %s)", (skills_str, filename, resume_data))
        db_connection.commit()

    return render_template('qns.html', skills=extracted_skills)


@app.route('/generate_questions', methods=['POST'])
def generate_questions():
    selected_skills = request.form.getlist('selected_skills[]')
    skill_level = request.form.get('level')
    question_mode = request.form.get('question_mode')
    num_questions = int(request.form.get('num_questions'))
    generated_questions = []

    # Dummy questions for different skill levels
    beginner_questions = {'Beginner question 1', 'Beginner question 2', 'Beginner question 3'}
    intermediate_questions = {'Intermediate question 1', 'Intermediate question 2', 'Intermediate question 3'}
    advanced_questions = {'Advanced question 1', 'Advanced question 2', 'Advanced question 3'}

    # Generate questions based on skill level
    if skill_level == 'beginner':
        questions_for_skills = {skill: beginner_questions for skill in selected_skills}
    elif skill_level == 'intermediate':
        questions_for_skills = {skill: intermediate_questions for skill in selected_skills}
    elif skill_level == 'advanced':
        questions_for_skills = {skill: advanced_questions for skill in selected_skills}
    else:
        return 'Invalid skill level'

    # Generate questions for selected skills
    generated_questions = generate_questions_for_skills(questions_for_skills, question_mode, num_questions)

    return render_template('qns.html', skills=selected_skills, questions=generated_questions)


if __name__ == '__main__':
    app.run(debug=True)
