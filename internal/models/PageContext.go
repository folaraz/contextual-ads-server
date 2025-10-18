package models

import (
	"encoding/json"
)

type JSONStringSlice []string

func (s *JSONStringSlice) UnmarshalBinary(data []byte) error {
	return json.Unmarshal(data, s)
}

type JSONFloat32Slice []float32

func (f *JSONFloat32Slice) UnmarshalBinary(data []byte) error {
	return json.Unmarshal(data, f)
}

type JSONStringMap map[string]string

func (m *JSONStringMap) UnmarshalBinary(data []byte) error {
	return json.Unmarshal(data, m)
}

type JSONChunkContextSlice []ChunkContext

func (c *JSONChunkContextSlice) UnmarshalBinary(data []byte) error {
	return json.Unmarshal(data, c)
}

type PageContext struct {
	Keywords      JSONStringSlice       `redis:"keywords"`
	Entities      JSONStringSlice       `redis:"entities"`
	Topics        JSONStringSlice       `redis:"topics"`
	Embedding     JSONFloat32Slice      `redis:"embedding"`
	Metadata      JSONStringMap         `redis:"metadata"`
	ChunkContexts JSONChunkContextSlice `redis:"chunk_context"`
}

type ChunkContext struct {
	Embedding []float32 `redis:"embedding"`
	ChunkText string    `redis:"chunk_text"`
}
