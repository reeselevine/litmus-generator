using namespace std;

int check_rr(vector<uint32_t> results) {
  cout << "flag=1, r0=2, r1=2 (seq): " << results[0] << "\n";
  cout << "flag=0, r0=2, r1=2 (seq): " << results[1] << "\n";
  cout << "flag=1, r0=1, r1=1 (interleaved): " << results[2] << "\n";
  cout << "flag=0, r0=1, r1=1 (interleaved): " << results[3] << "\n";
  cout << "flag=0, r0=2, r1=1 (racy): " << results[4] << "\n";
  cout << "flag=0, r0=1, r1=2 (racy): " << results[5] << "\n";
  cout << "flag=1, r0=2, r1=1 (not bound): " << results[6] << "\n";
  cout << "flag=1, r0=1, r1=2 (not bound): " << results[7] << "\n";
  cout << "Other/error: " << results[8] << "\n\n";
  return results[6] + results[7] + results[8];
}

int check_rw(vector<uint32_t> results) {
  cout << "flag=1, r0=2, mem=3 (seq): " << results[0] << "\n";
  cout << "flag=0, r0=2, mem=1 (seq): " << results[1] << "\n";
  cout << "flag=1, r0=1, mem=3 (interleaved): " << results[2] << "\n";
  cout << "flag=0, r0=1, mem=3 (interleaved): " << results[3] << "\n";
  cout << "flag=0, r0=2, mem=3 (interleaved): " << results[4] << "\n";
  cout << "flag=0, r0=1, mem=1 (racy): " << results[5] << "\n";
  cout << "flag=1, r0=2, mem=1 (not bound): " << results[6] << "\n";
  cout << "flag=1, r0=1, mem=1 (not bound): " << results[7] << "\n";
  cout << "Other/error: " << results[8] << "\n\n";
  return results[6] + results[7] + results[8];
}

int check_wr(vector<uint32_t> results) {
  cout << "flag=1, r0=3, mem=3 (seq): " << results[0] << "\n";
  cout << "flag=0, r0=3, mem=1 (seq): " << results[1] << "\n";
  cout << "flag=0, r0=1, mem=1 (interleaved): " << results[2] << "\n";
  cout << "flag=0, r0=3, mem=3 (interleaved): " << results[3] << "\n";
  cout << "flag=1, r0=1, mem=1 (not bound): " << results[4] << "\n";
  cout << "Other/error: " << results[5] << "\n\n";
  return results[4] +  results[5];
}

int check_results(vector<uint32_t> results, string test_name) {
  if (test_name == "rr") {
    return check_rr(results);
  } else if (test_name == "rw") {
    return check_rw(results);
  } else if (test_name == "wr") {
    return check_wr(results);
  }
  return false;
}
