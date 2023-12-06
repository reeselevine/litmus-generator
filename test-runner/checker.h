using namespace std;

int check_mp(vector<uint32_t> results) {
  cout << "r0=0, r1=0 (seq): " << results[0] << "\n";
  cout << "r0=1, r1=1 (seq): " << results[1] << "\n";
  cout << "r0=0, r1=1 (interleaved): " << results[2] << "\n";
  cout << "r0=1, r1=0 (weak): " << results[3] << "\n";
  return results[3];
}

int check_results(vector<uint32_t> results, string test_name) {
  if (test_name == "mp") {
    return check_rr(results);
  }
  return -1;
}
