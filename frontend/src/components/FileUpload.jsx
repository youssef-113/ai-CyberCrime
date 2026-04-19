import { useState } from 'react'
import { motion } from 'framer-motion'
import { Upload, FileImage, FileText, X } from 'lucide-react'

function FileUpload({ onUpload }) {
  const [dragActive, setDragActive] = useState(false)
  const [files, setFiles] = useState([])

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files)
    }
  }

  const handleChange = (e) => {
    e.preventDefault()
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files)
    }
  }

  const handleFiles = (fileList) => {
    const newFiles = Array.from(fileList).map(file => ({
      id: Date.now() + Math.random(),
      file,
      name: file.name,
      type: file.type,
      size: (file.size / 1024).toFixed(2) + ' KB'
    }))
    setFiles(prev => [...prev, ...newFiles])
  }

  const removeFile = (id) => {
    setFiles(files.filter(f => f.id !== id))
  }

  const handleSubmit = () => {
    onUpload(files)
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-cyber-blue">Upload Your Evidence</h2>
      
      <div
        className={`border-2 border-dashed rounded-xl p-12 text-center transition-all duration-300 ${
          dragActive 
            ? 'border-cyber-blue bg-cyber-blue/10' 
            : 'border-white/20 hover:border-cyber-blue/50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload className="w-16 h-16 mx-auto mb-4 text-cyber-blue" />
        <p className="text-xl mb-2">Drag & drop your files here</p>
        <p className="text-gray-400 mb-4">or click to browse</p>
        <input
          type="file"
          multiple
          accept="image/*,.pdf"
          onChange={handleChange}
          className="hidden"
          id="file-upload"
        />
        <label
          htmlFor="file-upload"
          className="cyber-button inline-block cursor-pointer"
        >
          Select Files
        </label>
        <p className="text-sm text-gray-500 mt-4">
          Supports: Screenshots, Images, PDFs
        </p>
      </div>

      {files.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <h3 className="font-semibold mb-4">Uploaded Files ({files.length})</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {files.map((file) => (
              <motion.div
                key={file.id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-card p-4 flex items-center justify-between"
              >
                <div className="flex items-center space-x-3">
                  {file.type.startsWith('image/') ? (
                    <FileImage className="w-8 h-8 text-cyber-blue" />
                  ) : (
                    <FileText className="w-8 h-8 text-cyber-purple" />
                  )}
                  <div>
                    <p className="font-medium truncate max-w-xs">{file.name}</p>
                    <p className="text-sm text-gray-400">{file.size}</p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(file.id)}
                  className="text-gray-400 hover:text-red-400 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </motion.div>
            ))}
          </div>
          
          <div className="flex justify-center mt-6">
            <button
              onClick={handleSubmit}
              className="cyber-button flex items-center space-x-2 text-lg px-8 py-4"
            >
              <span>Analyze Evidence</span>
            </button>
          </div>
        </motion.div>
      )}
    </div>
  )
}

export default FileUpload
