import numpy as np
import networkx as nx
import PyPDF2
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# Download required NLTK data
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file."""
    reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def preprocess_text(text):
    """Clean and preprocess the text."""
    # Remove special characters and extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.]', '', text)
    return text.strip()

def lemmatize_text(text):
    """Lemmatize the text."""
    lemmatizer = WordNetLemmatizer()
    return ' '.join([lemmatizer.lemmatize(word) for word in word_tokenize(text)])

def advanced_textrank_summarize(text, num_sentences=15):
    """Generate summary using an advanced TextRank algorithm."""
    sentences = sent_tokenize(text)
    
    if len(sentences) <= num_sentences:
        return sentences
    
    stop_words = set(stopwords.words('english'))
    
    # Lemmatize and clean sentences
    clean_sentences = [lemmatize_text(preprocess_text(sent.lower())) for sent in sentences]
    
    # Create similarity matrix
    similarity_matrix = np.zeros((len(sentences), len(sentences)))
    for i, sent1 in enumerate(clean_sentences):
        for j, sent2 in enumerate(clean_sentences):
            if i != j:
                words1 = set(word_tokenize(sent1)) - stop_words
                words2 = set(word_tokenize(sent2)) - stop_words
                similarity = len(words1.intersection(words2)) / (np.log(len(words1)) + np.log(len(words2)))
                similarity_matrix[i][j] = similarity
    
    # Create network graph
    nx_graph = nx.from_numpy_array(similarity_matrix)
    scores = nx.pagerank(nx_graph)
    
    # Get top sentences
    ranked_sentences = sorted(((scores[i], sentence) for i, sentence in enumerate(sentences)), reverse=True)
    
    # Select top N sentences and sort them by their original position
    top_sentences = sorted(ranked_sentences[:num_sentences], key=lambda x: sentences.index(x[1]))
    
    return [sent for _, sent in top_sentences]

def format_summary_as_points(summary_sentences):
    """Format the summary sentences as bullet points with spacing."""
    points = []
    for sentence in summary_sentences:
        points.append(f"• {sentence}\n")
    return points

def summarize_pdf(pdf_path, num_sentences=15):
    """Main function to summarize PDF."""
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        # Clean text
        clean_text = preprocess_text(text)
        
        # Generate summary using advanced TextRank approach
        summary_sentences = advanced_textrank_summarize(clean_text, num_sentences)
        
        # Format summary as bullet points
        summary_points = format_summary_as_points(summary_sentences)
        
        # Calculate word counts
        original_word_count = len(text.split())
        summary_word_count = sum(len(point.split()) for point in summary_points)
        
        return {
            "success": True,
            "summary": summary_points,
            "originalLength": original_word_count,
            "summaryLength": summary_word_count
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def format_summary_as_paragraphs(summary_sentences, sentences_per_paragraph=5):
    """Format the summary sentences as paragraphs."""
    paragraphs = []
    for i in range(0, len(summary_sentences), sentences_per_paragraph):
        paragraph = ' '.join(summary_sentences[i:i+sentences_per_paragraph])
        paragraphs.append(paragraph)
    return paragraphs


@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400

    if file and file.filename.lower().endswith('.pdf'):
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        # Set number of sentences to ensure at least 400 words
        num_sentences = 15  # This should typically result in more than 400 words

        # Summarize the PDF
        result = summarize_pdf(file_path, num_sentences)
        
        # Clean up the uploaded file
        os.remove(file_path)
        
        return jsonify(result), 200 if result["success"] else 500

    return jsonify({"success": False, "error": "Unsupported file type"}), 400

if __name__ == '__main__':
    app.run(debug=True)