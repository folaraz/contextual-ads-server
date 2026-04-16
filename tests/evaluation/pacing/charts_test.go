package pacing

import (
	"fmt"
	"image/color"
	"os"
	"path/filepath"

	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/vg"
)

type ChartData struct {
	Campaigns    []campaignSetup
	Snapshots    []pacingSnapshot
	NumIntervals int
	PacingEveryN int
	OutputDir    string
}

var campaignColors = []color.RGBA{
	{R: 31, G: 119, B: 180, A: 255},
	{R: 255, G: 127, B: 14, A: 255},
	{R: 44, G: 160, B: 44, A: 255},
	{R: 214, G: 39, B: 40, A: 255},
	{R: 148, G: 103, B: 189, A: 255},
	{R: 140, G: 86, B: 75, A: 255},
	{R: 227, G: 119, B: 194, A: 255},
	{R: 127, G: 127, B: 127, A: 255},
	{R: 188, G: 189, B: 34, A: 255},
	{R: 23, G: 190, B: 207, A: 255},
}

func GeneratePacingCharts(data ChartData) ([]string, error) {
	if err := os.MkdirAll(data.OutputDir, 0o755); err != nil {
		return nil, fmt.Errorf("creating output dir: %w", err)
	}

	generators := []func(ChartData) (string, error){
		generateMultiplierTrajectoryChart,
		generateCumulativeSpendChart,
		generateSpendRateChart,
		generateBudgetErrorChart,
	}

	var paths []string
	for _, gen := range generators {
		path, err := gen(data)
		if err != nil {
			return paths, err
		}
		paths = append(paths, path)
	}
	return paths, nil
}

func snapshotsForCampaign(snapshots []pacingSnapshot, campaignID int32) []pacingSnapshot {
	var result []pacingSnapshot
	for _, s := range snapshots {
		if s.CampaignID == campaignID {
			result = append(result, s)
		}
	}
	return result
}

var campaignLabels = map[int32]string{
	1:  "C1 Small $5K",
	2:  "C2 Medium $25K",
	3:  "C3 Large $50K",
	5:  "C5 Premium $10K",
	7:  "C7 Sprint $1.5K",
	8:  "C8 Whale $500K",
	10: "C10 LongTail $70K",
}

func campaignLabel(cs campaignSetup) string {
	if label, ok := campaignLabels[cs.CampaignID]; ok {
		return label
	}
	return fmt.Sprintf("Campaign %d ($%dK)", cs.CampaignID, int(cs.TotalBudget/1000))
}

func generateMultiplierTrajectoryChart(data ChartData) (string, error) {
	p := plot.New()
	p.Title.Text = "Pacing Multiplier Trajectory"
	p.X.Label.Text = "Pacing Cycle"
	p.Y.Label.Text = "Multiplier"
	p.Y.Min = 0
	p.Y.Max = 2.5
	p.Add(plotter.NewGrid())

	for i, cs := range data.Campaigns {
		snaps := snapshotsForCampaign(data.Snapshots, cs.CampaignID)
		if len(snaps) == 0 {
			continue
		}

		pts := make(plotter.XYs, len(snaps))
		for j, s := range snaps {
			pts[j] = plotter.XY{X: float64(j), Y: s.Multiplier}
		}

		line, err := plotter.NewLine(pts)
		if err != nil {
			return "", fmt.Errorf("creating line for campaign %d: %w", cs.CampaignID, err)
		}
		line.LineStyle.Color = campaignColors[i%len(campaignColors)]
		line.LineStyle.Width = vg.Points(2)
		p.Add(line)
		p.Legend.Add(campaignLabel(cs), line)

		if i == 0 {
			maxCycle := float64(len(snaps) - 1)
			addHorizontalDashed(p, 0.5, maxCycle, color.RGBA{R: 150, G: 150, B: 150, A: 200}, "Min (0.5)")
			addHorizontalDashed(p, 2.0, maxCycle, color.RGBA{R: 150, G: 150, B: 150, A: 200}, "Max (2.0)")
		}
	}

	p.Legend.Top = true

	outPath := filepath.Join(data.OutputDir, "multiplier_trajectory.png")
	if err := p.Save(12*vg.Inch, 6*vg.Inch, outPath); err != nil {
		return "", fmt.Errorf("saving multiplier chart: %w", err)
	}
	return outPath, nil
}

func generateCumulativeSpendChart(data ChartData) (string, error) {
	p := plot.New()
	p.Title.Text = "Cumulative Spend vs Ideal Linear Spend"
	p.X.Label.Text = "Pacing Cycle"
	p.Y.Label.Text = "Spend ($)"
	p.Add(plotter.NewGrid())

	for i, cs := range data.Campaigns {
		snaps := snapshotsForCampaign(data.Snapshots, cs.CampaignID)
		if len(snaps) == 0 {
			continue
		}

		pts := make(plotter.XYs, len(snaps))
		for j, s := range snaps {
			pts[j] = plotter.XY{X: float64(j), Y: float64(s.SpendCents) / 100.0}
		}

		line, err := plotter.NewLine(pts)
		if err != nil {
			return "", fmt.Errorf("creating spend line for campaign %d: %w", cs.CampaignID, err)
		}
		line.LineStyle.Color = campaignColors[i%len(campaignColors)]
		line.LineStyle.Width = vg.Points(2)
		p.Add(line)
		p.Legend.Add(campaignLabel(cs)+" actual", line)

		idealPts := make(plotter.XYs, 2)
		idealPts[0] = plotter.XY{X: 0, Y: 0}
		idealPts[1] = plotter.XY{X: float64(len(snaps) - 1), Y: cs.DailyBudget}

		idealLine, err := plotter.NewLine(idealPts)
		if err != nil {
			return "", fmt.Errorf("creating ideal line for campaign %d: %w", cs.CampaignID, err)
		}
		idealLine.LineStyle.Color = campaignColors[i%len(campaignColors)]
		idealLine.LineStyle.Width = vg.Points(1.5)
		idealLine.LineStyle.Dashes = []vg.Length{vg.Points(6), vg.Points(3)}
		p.Add(idealLine)
		p.Legend.Add(campaignLabel(cs)+" ideal", idealLine)
	}

	p.Legend.Top = true

	outPath := filepath.Join(data.OutputDir, "cumulative_spend.png")
	if err := p.Save(12*vg.Inch, 6*vg.Inch, outPath); err != nil {
		return "", fmt.Errorf("saving spend chart: %w", err)
	}
	return outPath, nil
}

func generateSpendRateChart(data ChartData) (string, error) {
	p := plot.New()
	p.Title.Text = "Spend Rate per Pacing Cycle"
	p.X.Label.Text = "Pacing Cycle"
	p.Y.Label.Text = "Spend per Cycle ($)"
	p.Add(plotter.NewGrid())

	for i, cs := range data.Campaigns {
		snaps := snapshotsForCampaign(data.Snapshots, cs.CampaignID)
		if len(snaps) < 2 {
			continue
		}

		pts := make(plotter.XYs, len(snaps)-1)
		for j := 1; j < len(snaps); j++ {
			delta := float64(snaps[j].SpendCents-snaps[j-1].SpendCents) / 100.0
			if delta < 0 {
				delta = 0
			}
			pts[j-1] = plotter.XY{X: float64(j), Y: delta}
		}

		line, err := plotter.NewLine(pts)
		if err != nil {
			return "", fmt.Errorf("creating rate line for campaign %d: %w", cs.CampaignID, err)
		}
		line.LineStyle.Color = campaignColors[i%len(campaignColors)]
		line.LineStyle.Width = vg.Points(1.5)
		p.Add(line)
		p.Legend.Add(campaignLabel(cs), line)
	}

	p.Legend.Top = true

	outPath := filepath.Join(data.OutputDir, "spend_rate.png")
	if err := p.Save(12*vg.Inch, 6*vg.Inch, outPath); err != nil {
		return "", fmt.Errorf("saving rate chart: %w", err)
	}
	return outPath, nil
}

func generateBudgetErrorChart(data ChartData) (string, error) {
	p := plot.New()
	p.Title.Text = "Cumulative Budget Error Over Time"
	p.X.Label.Text = "Pacing Cycle"
	p.Y.Label.Text = "Cumulative Error ($)  [actual - ideal]"
	p.Add(plotter.NewGrid())

	var maxCycles float64

	for i, cs := range data.Campaigns {
		snaps := snapshotsForCampaign(data.Snapshots, cs.CampaignID)
		if len(snaps) == 0 {
			continue
		}
		if float64(len(snaps)-1) > maxCycles {
			maxCycles = float64(len(snaps) - 1)
		}

		totalCycles := float64(len(snaps))
		pts := make(plotter.XYs, len(snaps))
		for j, s := range snaps {
			actualSpend := float64(s.SpendCents) / 100.0
			idealSpend := cs.DailyBudget * (float64(j) / totalCycles)
			pts[j] = plotter.XY{X: float64(j), Y: actualSpend - idealSpend}
		}

		line, err := plotter.NewLine(pts)
		if err != nil {
			return "", fmt.Errorf("creating error line for campaign %d: %w", cs.CampaignID, err)
		}
		line.LineStyle.Color = campaignColors[i%len(campaignColors)]
		line.LineStyle.Width = vg.Points(2)
		p.Add(line)
		p.Legend.Add(campaignLabel(cs), line)
	}

	if maxCycles > 0 {
		addHorizontalDashed(p, 0, maxCycles, color.RGBA{R: 100, G: 100, B: 100, A: 180}, "Zero (ideal)")
	}

	p.Legend.Top = true

	outPath := filepath.Join(data.OutputDir, "budget_error.png")
	if err := p.Save(12*vg.Inch, 6*vg.Inch, outPath); err != nil {
		return "", fmt.Errorf("saving budget error chart: %w", err)
	}
	return outPath, nil
}

func addHorizontalDashed(p *plot.Plot, yVal, maxX float64, c color.RGBA, label string) {
	pts := plotter.XYs{
		{X: 0, Y: yVal},
		{X: maxX, Y: yVal},
	}
	line, err := plotter.NewLine(pts)
	if err != nil {
		return
	}
	line.LineStyle.Color = c
	line.LineStyle.Width = vg.Points(1)
	line.LineStyle.Dashes = []vg.Length{vg.Points(4), vg.Points(4)}
	line.LineStyle.DashOffs = vg.Points(0)
	p.Add(line)
	p.Legend.Add(label, line)
}
