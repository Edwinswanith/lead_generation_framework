# You may need to install a library to read .docx files:    
# pip install python-docx
import docx


def read_local_doc(file_path):  
    """
    Read content from a local document file (.docx)
    
    Args:
        file_path (str): Path to the local document file
    
    Returns:
        str: Content of the document file
    """
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
        
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def read_doc(file_path):
    content = read_local_doc(file_path)
    
    return content
