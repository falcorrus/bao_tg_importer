import paramiko
import os

def check_files():
    hostname = "148.230.107.136"
    username = "root"
    password = "Gregarious1H"
    
    print(f"Connecting to {hostname}...")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, username=username, password=password)
        
        print("\n--- Listing /root/ ---")
        stdin, stdout, stderr = client.exec_command("ls -F /root/")
        print(stdout.read().decode())
        
        print("\n--- Listing /root/scripts/ ---")
        stdin, stdout, stderr = client.exec_command("ls -F /root/scripts/")
        print(stdout.read().decode())
        
        client.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_files()

