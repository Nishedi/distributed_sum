#include <vector>

extern "C" {

double sum_array(double* arr, int n) {
    double sum = 0;
    for(int i = 0; i < n; ++i) sum += arr[i];
    return sum;
}

}
