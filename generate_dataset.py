import os
import sys
import json
import bench_utils

def extract_node_mapping(bench_path):
    """Assigns an integer index to each node to mimic standard graph ML indexing."""
    node_to_name = {}
    idx = 0
    
    with open(bench_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('INPUT('):
                name = line.split('(')[1].split(')')[0].strip()
                node_to_name[idx] = name
                idx += 1
            elif '=' in line:
                name = line.split('=')[0].strip()
                if ':' in name:
                    name = name.split(':', 1)[1].strip()
                node_to_name[idx] = name
                idx += 1
                
    return node_to_name

def process_bench_file(bench_path):
    print(f"Extracting logic descriptions from {bench_path}...")
    
    node_to_name = extract_node_mapping(bench_path)
    pi_list, _, _ = bench_utils._parse_bench(bench_path)
    pi_set = set(pi_list)
    
    dataset_entries = []
    
    for node_idx, node_name in node_to_name.items():
        if node_name in pi_set:
            continue # Skip PIs as they have no fan-in logic
            
        try:
            fanin_pis = bench_utils.get_inputs(bench_path, node_name)
            
            # Limit inputs to avoid exponential memory blowup on truth tables
            if 0 < len(fanin_pis) <= 6:
                tt, num_inputs, input_list = bench_utils.get_truth_table(bench_path, node_name)
                
                description = (
                    f"Internal node {node_name} evaluates a boolean function. "
                    f"Its structural fan-in cone depends strictly on {num_inputs} primary inputs: {', '.join(input_list)}. "
                    f"The integer representation of its local truth table is {tt}."
                )
                
                dataset_entries.append({
                    "node_embedding_index": node_idx,
                    "bench_node_name": node_name,
                    "text_description": description
                })
                
        except Exception as e:
            print(f"Skipped node {node_name}: {e}")
            
    return dataset_entries

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_dataset.py <file.bench>")
        sys.exit(1)
        
    target_file = sys.argv[1]
    
    if os.path.exists(target_file):
        data = process_bench_file(target_file)
        
        # Save output using the same base name as the bench file
        out_name = target_file.replace(".bench", "_dataset.json")
        with open(out_name, "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"Successfully generated {len(data)} descriptions. Saved to {out_name}")
    else:
        print(f"File {target_file} not found.")