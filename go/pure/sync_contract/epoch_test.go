package synccontract

import "testing"

func TestCanEvaluate(t *testing.T) {
	for _, c := range []struct {
		compiled, current uint64
		pure, want        bool
	}{
		{1, 1, true, true}, {1, 2, true, false},
		{2, 1, true, false}, {1, 1, false, false},
	} {
		if got := CanEvaluate(c.compiled, c.current, c.pure); got != c.want {
			t.Fatalf("CanEvaluate(%d, %d, %v) = %v", c.compiled, c.current, c.pure, got)
		}
	}
}
