import sys
import os
import torch
import deepgate

def sanitize_bench_for_deepgate(input_path, clean_path):
    """
    DeepGate's parser strictly expects A = GATE(B, C). 
    It crashes on aliases (A = B) and constants (A = vdd).
    This function cleans the bench file so DeepGate can safely read it.
    """
    with open(input_path, 'r') as f:
        lines = f.readlines()

    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            clean_lines.append(line)
            continue

        if '=' in stripped:
            lhs, rhs = [x.strip() for x in stripped.split('=', 1)]
            
            # If there are no parentheses, it's an alias or constant
            if '(' not in rhs:
                # Handle constants (vdd/gnd) by treating them as pseudo-inputs
                if rhs.lower() in ['gnd', '0', 'vdd', '1', 'vcc']:
                    clean_lines.insert(0, f"INPUT({lhs})\n")
                # Handle buffer aliases (e.g., new_n17 = a[0])
                else:
                    # Mathematically equivalent to a buffer, but DeepGate can parse it!
                    clean_lines.append(f"{lhs} = AND({rhs}, {rhs})\n")
            else:
                clean_lines.append(line)
        else:
            clean_lines.append(line)

    with open(clean_path, 'w') as f:
        f.writelines(clean_lines)
    return clean_path

def extract_embeddings(bench_path):
    print("Loading pre-trained DeepGate model...")
    model = deepgate.Model()
    model.load_pretrained()
    
    # 1. Create a DeepGate-safe, sanitized temporary bench file
    clean_bench_path = bench_path.replace('.bench', '_clean.bench')
    print(f"Sanitizing {bench_path} to prevent parser crashes...")
    sanitize_bench_for_deepgate(bench_path, clean_bench_path)
    
    # 2. Parse the sanitized file
    print(f"Parsing sanitized file: {clean_bench_path}...")
    parser = deepgate.BenchParser()
    graph = parser.read_bench(clean_bench_path)
    
    # 3. Run Inference
    print("Running inference to generate embeddings...")
    with torch.no_grad():
        hs, hf = model(graph)
        
    print(f"\n--- Results for {bench_path} ---")
    print(f"Total nodes in graph: {hs.shape[0]}")
    print(f"Embedding dimension: {hs.shape[1]}")
    
    # 4. Save the tensor and clean up the temporary file
    out_name = bench_path.replace('.bench', '_embeddings.pt')
    torch.save({'structural': hs, 'functional': hf}, out_name)
    print(f"Successfully saved embeddings to {out_name}")
    
    if os.path.exists(clean_bench_path):
        os.remove(clean_bench_path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 get_embeddings.py <file.bench>")
        sys.exit(1)
        
    extract_embeddings(sys.argv[1])