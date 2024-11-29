package chroma

import (
	"os"
	"path/filepath"

	"github.com/pkg/errors"
)

func CheckPersistDir(persistDir string) error {
	if persistDir == "" {
		return errors.New("persist directory is required")
	}
	if _, err := os.Stat(persistDir); os.IsNotExist(err) {
		return errors.Wrapf(err, "persist directory %s does not exist", persistDir)
	}
	chromaSqliteFile := filepath.Join(persistDir, "chroma.sqlite3")
	if _, err := os.Stat(chromaSqliteFile); os.IsNotExist(err) {
		return errors.Wrapf(err, "chroma.sqlite3 file does not exist in persist directory %s", persistDir)
	}
	return nil
}

func GetSegmentDirs(persistDir string) ([]string, error) {
	segmentDirs, err := os.ReadDir(persistDir)
	if err != nil {
		return nil, errors.Wrap(err, "failed to get segment dirs")
	}
	var dirs []string
	for _, dir := range segmentDirs {
		if dir.IsDir() && IsValidSegmentDir(filepath.Join(persistDir, dir.Name())) {
			dirs = append(dirs, dir.Name())
		}
	}
	return dirs, nil
}

func IsValidSegmentDir(segmentDir string) bool {
	headerFile := filepath.Join(segmentDir, "header.bin")
	if _, err := os.Stat(headerFile); os.IsNotExist(err) {
		return false
	}
	return true
}
