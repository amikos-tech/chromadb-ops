package cmd

import (
	"github.com/mitchellh/go-homedir"
	"github.com/spf13/cobra"
)

// RootCmd represents the base command when called without any subcommands
var RootCmd = &cobra.Command{
	Use:     "chops",
	Short:   "The Chroma Ops TUI.",
	Long:    `Utility to manage your Chroma DB instance.`,
	Version: "0.0.0",
}

type HomeDirProvider interface {
	GetHomeDir() (string, error)
}

type DefaultHomeDirProvider struct{}

func (d DefaultHomeDirProvider) GetHomeDir() (string, error) {
	return homedir.Dir()
}

func init() {
	RootCmd.Flags().BoolP("toggle", "t", false, "Help message for toggle")
}
