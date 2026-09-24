import os
import subprocess
import time
import sys

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_file = os.path.join(base_dir, "tigergraph", "schema", "schema.gsql")
    
    print("Checking TigerGraph container availability...")
    res = subprocess.run(['docker', 'exec', 'tigergraph', 'echo', 'OK'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print("TigerGraph container is not running. Please start it first.")
        sys.exit(1)
    
    print("Creating Schema...")
    with open(schema_file, 'r') as f:
        schema_code = f.read()
    
    process = subprocess.Popen(['docker', 'exec', '-i', 'tigergraph', 'gsql'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(input=schema_code.encode('utf-8'))
    print(out.decode('utf-8'))
    
    print("Waiting 15 seconds for schema to initialize...")
    time.sleep(15)
    
    print("Installing Queries...")
    query_file = os.path.join(base_dir, "tigergraph", "queries", "install_queries.gsql")
    with open(query_file, 'r') as f:
        query_code = f.read()
    
    process = subprocess.Popen(['docker', 'exec', '-i', 'tigergraph', 'gsql', '-g', 'FraudInvestigation'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(input=query_code.encode('utf-8'))
    print(out.decode('utf-8'))

if __name__ == "__main__":
    main()
