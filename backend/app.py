import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

from checkers.content_checker import check_content
from checkers.toc_checker import check_toc
from checkers.page_number_checker import check_page_numbers
from checkers.link_checker import check_links
from checkers.ligature_checker import check_ligatures

app = Flask(__name__)
CORS(app)

ALLOWED_WORD = {".docx"}
ALLOWED_PDF = {".pdf"}


def allowed_file(filename, allowed):
    return "." in filename and os.path.splitext(filename)[1].lower() in allowed


@app.route("/api/check", methods=["POST"])
def check_documents():
    if "word" not in request.files or "pdf" not in request.files:
        return jsonify({"error": "Both 'word' and 'pdf' files are required."}), 400

    word_file = request.files["word"]
    pdf_file = request.files["pdf"]

    if not allowed_file(word_file.filename, ALLOWED_WORD):
        return jsonify({"error": "Word file must be a .docx file."}), 400
    if not allowed_file(pdf_file.filename, ALLOWED_PDF):
        return jsonify({"error": "PDF file must be a .pdf file."}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        word_path = os.path.join(tmpdir, "source.docx")
        pdf_path = os.path.join(tmpdir, "design.pdf")

        word_file.save(word_path)
        pdf_file.save(pdf_path)

        try:
            content_result = check_content(word_path, pdf_path)
        except Exception as e:
            content_result = {"passed": False, "error": str(e)}

        try:
            toc_result = check_toc(word_path, pdf_path)
        except Exception as e:
            toc_result = {"passed": False, "error": str(e)}

        try:
            page_result = check_page_numbers(pdf_path)
        except Exception as e:
            page_result = {"passed": False, "error": str(e)}

        try:
            link_result = check_links(pdf_path, word_path)
        except Exception as e:
            link_result = {"passed": False, "error": str(e)}

        try:
            ligature_result = check_ligatures(pdf_path)
        except Exception as e:
            ligature_result = {"passed": False, "error": str(e)}

    return jsonify({
        "content": content_result,
        "toc": toc_result,
        "page_numbers": page_result,
        "links": link_result,
        "ligatures": ligature_result,
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5050)
