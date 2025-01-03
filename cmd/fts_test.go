package cmd

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/stretchr/testify/require"

	chroma "github.com/amikos-tech/chroma-go"
	"github.com/amikos-tech/chroma-go/collection"
	"github.com/amikos-tech/chroma-go/types"
	wheredoc "github.com/amikos-tech/chroma-go/where_document"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/mount"
	testcontainers "github.com/testcontainers/testcontainers-go"
	tcchroma "github.com/testcontainers/testcontainers-go/modules/chroma"
	"github.com/testcontainers/testcontainers-go/wait"
)

func getChromaContainerAndClient(t *testing.T, chromaImage, chromaVersion, tempDir string, ctx context.Context) (*tcchroma.ChromaContainer, *chroma.Client) {
	chromaContainer, err := tcchroma.Run(ctx,
		fmt.Sprintf("%s:%s", chromaImage, chromaVersion),
		testcontainers.WithEnv(map[string]string{"ALLOW_RESET": "true"}),
		testcontainers.CustomizeRequest(testcontainers.GenericContainerRequest{
			ContainerRequest: testcontainers.ContainerRequest{
				WaitingFor: wait.ForAll(
					wait.ForListeningPort("8000/tcp"),
				),
				HostConfigModifier: func(hostConfig *container.HostConfig) {
					hostConfig.Mounts = []mount.Mount{
						{
							Type:   mount.TypeBind,
							Source: tempDir,
							Target: "/chroma/chroma",
						},
					}
				},
			},
		}),
	)
	require.NoError(t, err)
	endpoint, err := chromaContainer.RESTEndpoint(context.Background())
	require.NoError(t, err)
	chromaURL := os.Getenv("CHROMA_URL")
	if chromaURL == "" {
		chromaURL = endpoint
	}
	chromaClient, err := chroma.NewClient(chromaURL, chroma.WithDebug(true))
	require.NoError(t, err)
	return chromaContainer, chromaClient
}

func TestFtsRebuild(t *testing.T) {
	tempDir := t.TempDir()
	ctx := context.Background()
	var chromaVersion = "latest"
	var chromaImage = "ghcr.io/chroma-core/chroma"
	if os.Getenv("CHROMA_VERSION") != "" {
		chromaVersion = os.Getenv("CHROMA_VERSION")
	}
	if os.Getenv("CHROMA_IMAGE") != "" {
		chromaImage = os.Getenv("CHROMA_IMAGE")
	}
	chromaContainer, chromaClient := getChromaContainerAndClient(t, chromaImage, chromaVersion, tempDir, ctx)
	collection, err := chromaClient.NewCollection(ctx, collection.WithName("test"))
	require.NoError(t, err)
	documents := []string{
		"The quick brown fox jumps over the lazy dog",
		"Test time compute",
		"We've got all your llama's in a row",
		"Cats are lazy pets",
		"Dogs are loyal friends",
		"Birds are beautiful creatures",
		"Fish are fascinating underwater",
		"Bears are powerful animals",
		"Elephants are intelligent giants",
		"Tigers are majestic predators",
	}
	ids := []string{
		"ID1",
		"ID2",
		"ID3",
		"ID4",
		"ID5",
		"ID6",
		"ID7",
		"ID8",
		"ID9",
		"ID10",
	}
	embeddings := types.NewEmbeddingsFromFloat32([][]float32{
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
	})
	_, addError := collection.Add(context.Background(), embeddings, nil, documents, ids)
	require.NoError(t, addError)

	_, deleteError := collection.Delete(context.Background(), []string{"ID1"}, nil, nil)
	require.NoError(t, deleteError)
	wb := wheredoc.NewWhereDocumentBuilder()
	wb.Contains("compute")
	wmap, err := wb.Build()
	require.NoError(t, err)

	results, err := collection.Get(ctx, nil, wmap, nil, nil)
	require.NoError(t, err)
	require.Equal(t, 1, len(results.Ids))
	require.Equal(t, "ID2", results.Ids[0])
	stopDuration := 10 * time.Second
	err = chromaContainer.Stop(ctx, &stopDuration)
	require.NoError(t, err)
	RootCmd.SetArgs([]string{"fts", "rebuild", tempDir})
	err = RootCmd.ExecuteContext(ctx)
	require.NoError(t, err)

	chromaContainer, chromaClient = getChromaContainerAndClient(t, chromaImage, chromaVersion, tempDir, ctx)
	t.Cleanup(func() {
		if chromaContainer.IsRunning() {
			require.NoError(t, chromaContainer.Terminate(ctx))
		}
	})
	collection, err = chromaClient.GetCollection(ctx, "test", nil)
	require.NoError(t, err)
	results, err = collection.Get(ctx, nil, wmap, nil, nil)
	require.NoError(t, err)
	require.Equal(t, 1, len(results.Ids))
	require.Equal(t, "ID2", results.Ids[0])

}

func TestFtsChangeTokenizer(t *testing.T) {
	tempDir := t.TempDir()
	ctx := context.Background()
	var chromaVersion = "latest"
	var chromaImage = "ghcr.io/chroma-core/chroma"
	if os.Getenv("CHROMA_VERSION") != "" {
		chromaVersion = os.Getenv("CHROMA_VERSION")
	}
	if os.Getenv("CHROMA_IMAGE") != "" {
		chromaImage = os.Getenv("CHROMA_IMAGE")
	}
	chromaContainer, chromaClient := getChromaContainerAndClient(t, chromaImage, chromaVersion, tempDir, ctx)
	collection, err := chromaClient.NewCollection(ctx, collection.WithName("test"))
	require.NoError(t, err)
	documents := []string{
		"The quick brown fox jumps over the lazy dog",
		"We've got all your llama's in a row",
		"Cats are lazy pets",
		"Dogs are loyal friends",
		"Birds are beautiful creatures",
		"Fish are fascinating underwater",
		"Bears are powerful animals",
		"Elephants are intelligent giants",
		"주요 신흥 4개국 증시 외국인투자자 순매수액",
		"Tigers are majestic predators",
	}
	ids := []string{
		"ID1",
		"ID2",
		"ID3",
		"ID4",
		"ID5",
		"ID6",
		"ID7",
		"ID8",
		"ID9",
		"ID10",
	}
	embeddings := types.NewEmbeddingsFromFloat32([][]float32{
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
		{0.4, 0.5, 0.6},
		{0.7, 0.8, 0.9},
		{0.1, 0.2, 0.3},
	})
	_, addError := collection.Add(context.Background(), embeddings, nil, documents, ids)
	require.NoError(t, addError)

	_, deleteError := collection.Delete(context.Background(), []string{"ID1"}, nil, nil)
	require.NoError(t, deleteError)
	wb := wheredoc.NewWhereDocumentBuilder()
	wb.Contains("순매")
	wmap, err := wb.Build()
	require.NoError(t, err)
	results, err := collection.Get(ctx, nil, wmap, nil, nil)
	require.NoError(t, err)
	require.Equal(t, 0, len(results.Ids))
	err = chromaContainer.Terminate(ctx)
	require.NoError(t, err)

	t.Run("Test Wrong Tokenizer", func(t *testing.T) {
		RootCmd.SetArgs([]string{"fts", "rebuild", "-t", "wrong", tempDir})
		err = RootCmd.ExecuteContext(ctx)
		require.Error(t, err)
	})

	t.Run("Test Unicode61 Tokenizer", func(t *testing.T) {
		RootCmd.SetArgs([]string{"fts", "rebuild", "-t", "unicode61", tempDir})
		err = RootCmd.ExecuteContext(ctx)
		require.NoError(t, err)

		sqlFile := filepath.Join(tempDir, "chroma.sqlite3")
		db, err := sql.Open("sqlite3", "file:"+sqlFile+"?mode=rw")
		require.NoError(t, err)
		var sql string
		err = db.QueryRow("select sql from sqlite_master where name = 'embedding_fulltext_search'").Scan(&sql)
		require.NoError(t, err)
		require.Contains(t, sql, "tokenize='unicode61'")
		err = db.Close()
		require.NoError(t, err)

		chromaContainer, chromaClient = getChromaContainerAndClient(t, chromaImage, chromaVersion, tempDir, ctx)
		t.Cleanup(func() {
			if chromaContainer.IsRunning() {
				require.NoError(t, chromaContainer.Terminate(ctx))
			}
		})
		collection, err = chromaClient.GetCollection(ctx, "test", nil)
		require.NoError(t, err)
		results, err = collection.Get(ctx, nil, wmap, nil, nil)
		require.NoError(t, err)
		require.Equal(t, 1, len(results.Ids))
		require.Equal(t, "ID9", results.Ids[0])
		err = chromaContainer.Terminate(ctx)
		require.NoError(t, err)
	})

	t.Run("Test Ascii Tokenizer", func(t *testing.T) {

		RootCmd.SetArgs([]string{"fts", "rebuild", "-t", "ascii", tempDir})
		err = RootCmd.ExecuteContext(ctx)
		require.NoError(t, err)

		sqlFile := filepath.Join(tempDir, "chroma.sqlite3")
		db, err := sql.Open("sqlite3", "file:"+sqlFile+"?mode=rw")
		require.NoError(t, err)
		var sql string
		err = db.QueryRow("select sql from sqlite_master where name = 'embedding_fulltext_search'").Scan(&sql)
		require.NoError(t, err)
		require.Contains(t, sql, "tokenize='ascii'")
		err = db.Close()
		require.NoError(t, err)

		chromaContainer, chromaClient = getChromaContainerAndClient(t, chromaImage, chromaVersion, tempDir, ctx)
		t.Cleanup(func() {
			if chromaContainer.IsRunning() {
				require.NoError(t, chromaContainer.Terminate(ctx))
			}
		})
		collection, err = chromaClient.GetCollection(ctx, "test", nil)
		require.NoError(t, err)
		results, err = collection.Get(ctx, nil, wmap, nil, nil)
		require.NoError(t, err)
		require.Equal(t, 1, len(results.Ids))
		require.Equal(t, "ID9", results.Ids[0])
		err = chromaContainer.Terminate(ctx)
		require.NoError(t, err)
	})

}
