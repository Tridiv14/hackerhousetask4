import os
import subprocess
import sys

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_file = os.path.join(base_dir, "tigergraph", "loading", "load_transactions.gsql")
    
    print("Checking TigerGraph container availability...")
    res = subprocess.run(['docker', 'exec', 'tigergraph', 'echo', 'OK'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print("TigerGraph container is not running.")
        sys.exit(1)
        
    print("Copying data files to container...")
    data_dir = os.path.join(base_dir, "data", "raw")
    subprocess.run(['docker', 'exec', 'tigergraph', 'mkdir', '-p', '/home/tigergraph/mydata/raw'])
    
    files_to_copy = ["transactions.csv", "identity.csv", "closed_cases_history.csv", "case_pack.csv"]
    for f in files_to_copy:
        src = os.path.join(data_dir, f)
        if os.path.exists(src):
            subprocess.run(['docker', 'cp', src, f'tigergraph:/home/tigergraph/mydata/raw/{f}'])
        else:
            print(f"WARNING: File not found {src}")
            if f == "transactions.csv":
                print("ERROR: transactions.csv is required. It is an INPUT DATASET and must exist.")
                sys.exit(1)
                
    print("Creating Loading Job...")
    with open(load_file, 'r') as f:
        load_code = f.read()
    load_code = load_code.replace('$sys.data_root', '/home/tigergraph/mydata/raw')
    
    process = subprocess.Popen(['docker', 'exec', '-i', 'tigergraph', 'gsql', '-g', 'FraudInvestigation'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, err = process.communicate(input=load_code.encode('utf-8'))
    print(out.decode('utf-8'))
    
    print("Running Loading Job...")
    run_cmd = "USE GRAPH FraudInvestigation\nRUN LOADING JOB load_transactions\n"
    process = subprocess.Popen(['docker', 'exec', '-i', 'tigergraph', 'gsql', '-g', 'FraudInvestigation'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, err = process.communicate(input=run_cmd.encode('utf-8'))
    print(out.decode('utf-8'))
    
    print("Verifying Vertex Counts...")
    vertex_test = "USE GRAPH FraudInvestigation\nSELECT count() FROM Customer\nSELECT count() FROM Transaction"
    process = subprocess.Popen(['docker', 'exec', '-i', 'tigergraph', 'gsql', '-g', 'FraudInvestigation'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, err = process.communicate(input=vertex_test.encode('utf-8'))
    print(out.decode('utf-8'))

if __name__ == "__main__":
    main()

