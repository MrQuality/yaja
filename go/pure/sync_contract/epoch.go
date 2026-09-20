// Package synccontract contains pure schema-epoch decisions, with no I/O.
package synccontract

// CanEvaluate permits provisional evaluation only at the exact current epoch.
func CanEvaluate(compiled, current uint64, pure bool) bool {
	return pure && compiled == current
}
