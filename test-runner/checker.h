using namespace std;

int check_mp(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=0, r1=0 (seq): " << results[0] << "\n";
    cout << "r0=1, r1=1 (seq): " << results[1] << "\n";
    cout << "r0=0, r1=1 (interleaved): " << results[2] << "\n";
    cout << "r0=1, r1=0 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_lb(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, r1=0 (seq): " << results[0] << "\n";
    cout << "r0=0, r1=1 (seq): " << results[1] << "\n";
    cout << "r0=0, r1=0 (interleaved): " << results[2] << "\n";
    cout << "r0=1, r1=1 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_sb(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, r1=0 (seq): " << results[0] << "\n";
    cout << "r0=0, r1=1 (seq): " << results[1] << "\n";
    cout << "r0=1, r1=1 (interleaved): " << results[2] << "\n";
    cout << "r0=0, r1=0 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_22w(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "x=1, y=2 (seq): " << results[0] << "\n";
    cout << "x=2, y=1 (seq): " << results[1] << "\n";
    cout << "x=1, y=1 (interleaved): " << results[2] << "\n";
    cout << "x=2, y=2 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_store(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, x=1 (seq): " << results[0] << "\n";
    cout << "r0=0, x=2 (seq): " << results[1] << "\n";
    cout << "r0=0, x=1 (interleaved): " << results[2] << "\n";
    cout << "r0=1, x=2 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_read(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, y=2 (seq): " << results[0] << "\n";
    cout << "r0=0, y=1 (seq): " << results[1] << "\n";
    cout << "r0=1, y=1 (interleaved): " << results[2] << "\n";
    cout << "r0=0, y=2 (weak): " << results[3] << "\n";
  }
  return results[3];
}

int check_iriw(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=0, r1=0, r2=0, r3=0 (seq): " << results[0] << "\n";
    cout << "r0=1, r1=1, r2=1, r3=1 (seq): " << results[1] << "\n";
    cout << "r0=0, r1=0, r2=1, r3=1 (seq): " << results[2] << "\n";
    cout << "r0=1, r1=1, r2=0, r3=0 (seq): " << results[3] << "\n";
    cout << "r0 == r1, r2 != r3 (seq/interleaved): " << results[4] << "\n";
    cout << "r0 != r1, r2 == r3 (interleaved/seq): " << results[5] << "\n";
    cout << "r0=0, r1=1, r2=0, r3=1 (interleaved): " << results[6] << "\n";
    cout << "r0=0, r1=1, r2=1, r3=0 (interleaved): " << results[7] << "\n";
    cout << "r0=1, r1=0, r2=0, r3=1 (interleaved): " << results[8] << "\n";
    cout << "r0=1, r1=0, r2=1, r3=0 (weak): " << results[9] << "\n";
    cout << "other: " << results[10] << "\n";
  }
  return results[9];
}

int check_wrc(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, r1=1, r2=1 (seq): " << results[0] << "\n";
    cout << "r0=0, r1=0, r2=0 (seq): " << results[1] << "\n";
    cout << "r0=0, r1=0, r2=1 (seq): " << results[2] << "\n";
    cout << "r0=1, r1=0, r2=0 (seq): " << results[3] << "\n";
    cout << "r0=1, r1=0, r2=1 (interleaved): " << results[4] << "\n";
    cout << "r0=1, r1=1, r2=0 (weak): " << results[5] << "\n";
    cout << "other: " << results[6] << "\n";
  }
  return results[5];
}

int check_isa2(vector<uint32_t> results, bool print) {
  if (print) {
    cout << "r0=1, r1=1, r2=1 (seq): " << results[0] << "\n";
    cout << "r0=0, r1=0, r2=0 (seq): " << results[1] << "\n";
    cout << "r0=0, r1=0, r2=1 (seq): " << results[2] << "\n";
    cout << "r0=1, r1=0, r2=0 (seq): " << results[3] << "\n";
    cout << "r0=1, r1=0, r2=1 (interleaved): " << results[4] << "\n";
    cout << "r0=1, r1=1, r2=0 (weak): " << results[5] << "\n";
    cout << "other: " << results[6] << "\n";
  }
  return results[5];
}

int check_results(vector<uint32_t> results, string test_name, bool print) {
  if (test_name == "mp") {
    return check_mp(results, print);
  } else if (test_name == "lb") {
    return check_lb(results, print);
  } else if (test_name == "sb") {
    return check_sb(results, print);
  } else if (test_name == "read") {
    return check_read(results, print);
  } else if (test_name == "store") {
    return check_store(results, print);
  } else if (test_name == "iriw") {
    return check_iriw(results, print);
  } else if (test_name == "2+2w") {
    return check_22w(results, print);
  } else if (test_name == "wrc") {
    return check_wrc(results, print);
  } else if (test_name == "isa2") {
    return check_isa2(results, print);
  }
  return -1;
}
