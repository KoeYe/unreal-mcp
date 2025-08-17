import ast
import json
import sys

def parse_docstring(docstring):
    """Clean and format docstring"""
    if not docstring:
        return ""
    
    # Remove r""" prefix and clean up
    cleaned = docstring.strip()
    if cleaned.startswith('r"""') and cleaned.endswith('"""'):
        cleaned = cleaned[4:-3]
    elif cleaned.startswith('"""') and cleaned.endswith('"""'):
        cleaned = cleaned[3:-3]
    
    # Clean up extra whitespace
    lines = [line.strip() for line in cleaned.split('\n')]
    return ' '.join(line for line in lines if line)

def format_markdown_text(chunk_type, name, class_name, params, docstring):
    """Format chunk as markdown"""
    md_lines = []
    
    if chunk_type == "class":
        md_lines.append(f"## Class `{name}`")
        if docstring:
            md_lines.append(f"\n{docstring}")
    elif chunk_type == "method":
        md_lines.append(f"### Method `{class_name}.{name}()`")
        if params:
            md_lines.append(f"\n**Parameters:** `{', '.join(params)}`")
        if docstring:
            md_lines.append(f"\n**Description:** {docstring}")
    else:  # function
        md_lines.append(f"### Function `{name}()`")
        if params:
            md_lines.append(f"\n**Parameters:** `{', '.join(params)}`")
        if docstring:
            md_lines.append(f"\n**Description:** {docstring}")
    
    return '\n'.join(md_lines)

def chunk_python_file(file_path):
    """Parse Python file and extract chunks"""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    # Remove any remaining BOM characters and clean up
    content = content.lstrip('\ufeff')
    
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return []
    chunks = []
    
    def visit_node(node, class_name=None):
        if isinstance(node, ast.ClassDef):
            # Extract class
            docstring = parse_docstring(ast.get_docstring(node))
            
            markdown_text = format_markdown_text("class", node.name, None, None, docstring)
            
            chunk = {
                "id": f"class_{node.name}",
                "text": markdown_text,
                "metadata": {
                    "type": "class",
                    "name": node.name,
                    "docstring": docstring
                }
            }
            chunks.append(chunk)
            
            # Visit methods
            for child in node.body:
                visit_node(child, node.name)
                
        elif isinstance(node, ast.FunctionDef):
            # Extract function/method
            docstring = parse_docstring(ast.get_docstring(node))
            
            # Get parameters
            params = [arg.arg for arg in node.args.args]
            
            # Build markdown content
            if class_name:
                chunk_id = f"method_{class_name}_{node.name}"
                chunk_type = "method"
                markdown_text = format_markdown_text("method", node.name, class_name, params, docstring)
            else:
                chunk_id = f"function_{node.name}"
                chunk_type = "function"
                markdown_text = format_markdown_text("function", node.name, None, params, docstring)
            
            chunk = {
                "id": chunk_id,
                "text": markdown_text,
                "metadata": {
                    "type": chunk_type,
                    "name": node.name,
                    "class_name": class_name,
                    "parameters": params,
                    "docstring": docstring
                }
            }
            chunks.append(chunk)
        
        # Visit child nodes
        if hasattr(node, 'body'):
            for child in node.body:
                visit_node(child, class_name)
    
    visit_node(tree)
    return chunks

def save_to_markdown(chunks, output_path):
    """Save chunks to markdown file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# API Documentation\n\n")
        
        # Group by classes and standalone functions
        classes = {}
        functions = []
        
        for chunk in chunks:
            if chunk['metadata']['type'] == 'class':
                classes[chunk['metadata']['name']] = {
                    'class_chunk': chunk,
                    'methods': []
                }
            elif chunk['metadata']['type'] == 'method':
                class_name = chunk['metadata']['class_name']
                if class_name in classes:
                    classes[class_name]['methods'].append(chunk)
            else:  # function
                functions.append(chunk)
        
        # Write classes and their methods
        for class_name, class_data in classes.items():
            f.write(class_data['class_chunk']['text'] + '\n\n')
            
            for method in class_data['methods']:
                f.write(method['text'] + '\n\n')
        
        # Write standalone functions
        if functions:
            f.write("## Functions\n\n")
            for func in functions:
                f.write(func['text'] + '\n\n')

def main():
    if len(sys.argv) != 3:
        print("Usage: python chunker.py <input_file.py> <output_file.md>")
        return
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        chunks = chunk_python_file(input_file)
        save_to_markdown(chunks, output_file)
        print(f"Extracted {len(chunks)} chunks from {input_file}")
        print(f"Saved to {output_file}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()