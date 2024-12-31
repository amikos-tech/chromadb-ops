package cmd

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	chromadb "github.com/amikos-tech/chromadb-ops/internal/db"
	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
)

func setupDB(t *testing.T, schemaFile, persistDir string) *sql.DB {
	ctx := context.Background()
	sqlFile := filepath.Join(persistDir, "chroma.sqlite3")
	db, err := sql.Open("sqlite3", "file:"+sqlFile)
	require.NoError(t, err)

	schema, err := os.ReadFile(schemaFile)
	require.NoError(t, err)
	statements := strings.Split(string(schema), ";")
	for _, statement := range statements {
		statement = strings.TrimSpace(statement)
		lines := strings.Split(statement, "\n")
		executableStatement := ""
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "--") {
				continue
			}
			executableStatement += line + "\n"
		}
		_, err = db.ExecContext(ctx, executableStatement)
		require.NoError(t, err)
	}
	return db
}

func TestClean(t *testing.T) {
	tempdir := t.TempDir()
	ctx := context.Background()
	schemaFile := filepath.Join("..", "schema.sql")
	db := setupDB(t, schemaFile, tempdir)

	queries := chromadb.New(db)
	// create segment table

	segmentID := uuid.New().String()
	collectionID := uuid.New().String()
	err := queries.AddDummyVectorSegment(ctx, chromadb.AddDummyVectorSegmentParams{
		ID:         segmentID,
		Collection: collectionID,
	})
	require.NoError(t, err)

	segmentDir := filepath.Join(tempdir, segmentID)
	err = os.MkdirAll(filepath.Join(segmentDir, "header.bin"), 0o755)
	require.NoError(t, err)

	orphanedDir := filepath.Join(tempdir, uuid.New().String())
	err = os.MkdirAll(filepath.Join(orphanedDir, "header.bin"), 0o755)
	require.NoError(t, err)

	RootCmd.SetArgs([]string{"clean", tempdir})
	err = RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)
	require.DirExists(t, segmentDir)
	require.NoDirExists(t, orphanedDir)
}

func TestCleanDryRun(t *testing.T) {
	t.Cleanup(func() {
		RootCmd.SetArgs([]string{})
		err := CleanCommand.Flags().Set("dry-run", "false")
		require.NoError(t, err)
	})
	tempdir := t.TempDir()
	ctx := context.Background()
	schemaFile := filepath.Join("..", "schema.sql")
	db := setupDB(t, schemaFile, tempdir)

	queries := chromadb.New(db)
	// create segment table

	segmentID := uuid.New().String()
	collectionID := uuid.New().String()
	err := queries.AddDummyVectorSegment(ctx, chromadb.AddDummyVectorSegmentParams{
		ID:         segmentID,
		Collection: collectionID,
	})
	require.NoError(t, err)

	segmentDir := filepath.Join(tempdir, segmentID)
	err = os.MkdirAll(filepath.Join(segmentDir, "header.bin"), 0o755)
	require.NoError(t, err)

	orphanedDir := filepath.Join(tempdir, uuid.New().String())
	err = os.MkdirAll(filepath.Join(orphanedDir, "header.bin"), 0o755)
	require.NoError(t, err)

	RootCmd.SetArgs([]string{"clean", tempdir, "--dry-run"})

	err = RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)
	require.DirExists(t, segmentDir)
	require.DirExists(t, orphanedDir)
}

func TestCleanWithoutValidSegmentDir(t *testing.T) {
	tempdir := t.TempDir()
	ctx := context.Background()
	schemaFile := filepath.Join("..", "schema.sql")
	db := setupDB(t, schemaFile, tempdir)
	queries := chromadb.New(db)
	segmentID := uuid.New().String()
	collectionID := uuid.New().String()
	err := queries.AddDummyVectorSegment(ctx, chromadb.AddDummyVectorSegmentParams{
		ID:         segmentID,
		Collection: collectionID,
	})
	require.NoError(t, err)

	segmentDir := filepath.Join(tempdir, segmentID)
	err = os.MkdirAll(filepath.Join(segmentDir, "header.bin"), 0o755)
	require.NoError(t, err)

	orphanedDir := filepath.Join(tempdir, uuid.New().String())
	err = os.MkdirAll(orphanedDir, 0o755)
	require.NoError(t, err)

	RootCmd.SetArgs([]string{"clean", tempdir})
	err = RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)
	require.DirExists(t, segmentDir)
	require.DirExists(t, orphanedDir) // empty dir is not deleted as it is not a valid segment dir
}

func TestCleanEmptyDB(t *testing.T) {
	tempdir := t.TempDir()
	ctx := context.Background()
	schemaFile := filepath.Join("..", "schema.sql")
	_ = setupDB(t, schemaFile, tempdir)
	segmentID := uuid.New().String()
	segmentDir := filepath.Join(tempdir, segmentID)
	err := os.MkdirAll(filepath.Join(segmentDir, "header.bin"), 0o755)
	require.NoError(t, err)

	RootCmd.SetArgs([]string{"clean", tempdir})
	err = RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)
	require.NoDirExists(t, segmentDir)
}

func TestCleanEmptyDBNoSegmentDirs(t *testing.T) {
	tempdir := t.TempDir()
	ctx := context.Background()
	schemaFile := filepath.Join("..", "schema.sql")
	_ = setupDB(t, schemaFile, tempdir)

	RootCmd.SetArgs([]string{"clean", tempdir})
	err := RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)
}

func TestInvalidPersistDir(t *testing.T) {
	ctx := context.Background()
	tempdir := t.TempDir()
	RootCmd.SetArgs([]string{"clean", tempdir})
	err := RootCmd.ExecuteContext(ctx)
	require.Error(t, err)
}
