package main

import (
	"fmt"
	"os"

	"github.com/amikos-tech/chromadb-ops/cmd"
	"github.com/spf13/cobra"
)

var (
	Version   = "0.0.0"      // Replaced at build time
	BuildHash = "0000000"    // Replaced at build time
	BuildDate = "9999-12-31" // Replace with the actual build date
)

type ChromaOpsCLI struct {
	rootCmd         *cobra.Command
	homeDirProvider cmd.HomeDirProvider
}
type CliOption func(*ChromaOpsCLI) error

func WithHomeDirProvider(provider cmd.HomeDirProvider) CliOption {
	return func(c *ChromaOpsCLI) error {
		c.homeDirProvider = provider
		return nil
	}
}

func (c *ChromaOpsCLI) Initialize(options ...CliOption) error {
	for _, option := range options {
		err := option(c)
		if err != nil {
			return err
		}
	}
	c.rootCmd = cmd.RootCmd
	versionString := fmt.Sprintf("v%s-%s, build date %s\n", Version, BuildHash, BuildDate)
	c.rootCmd.SetVersionTemplate(versionString)

	err := c.rootCmd.Execute()
	if err != nil {
		return err
	}
	return nil
}

func main() {
	cli := &ChromaOpsCLI{}
	err := cli.Initialize(WithHomeDirProvider(cmd.DefaultHomeDirProvider{}))
	if err != nil {
		fmt.Printf("Error initializing CLI: %s", err)
		os.Exit(1)
	}
}
