import { Canvas } from '@react-three/fiber'
import { OrbitControls, Stars, Float, Text, MeshDistortMaterial } from '@react-three/drei'
import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'

function FloatingShield() {
  const meshRef = useRef()
  
  useFrame((state) => {
    meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.5) * 0.2
    meshRef.current.rotation.y = state.clock.elapsedTime * 0.3
  })

  return (
    <Float speed={2} rotationIntensity={1} floatIntensity={2}>
      <mesh ref={meshRef} scale={2}>
        <sphereGeometry args={[1, 32, 32]} />
        <MeshDistortMaterial
          color="#00d4ff"
          attach="material"
          distort={0.5}
          speed={2}
          roughness={0.2}
          metalness={0.8}
        />
      </mesh>
    </Float>
  )
}

function FloatingParticles() {
  const count = 50
  const positions = []
  
  for (let i = 0; i < count; i++) {
    positions.push([
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 20
    ])
  }

  return (
    <group>
      {positions.map((pos, i) => (
        <Float key={i} speed={1 + Math.random()} rotationIntensity={0.5} floatIntensity={1}>
          <mesh position={pos}>
            <sphereGeometry args={[0.05, 8, 8]} />
            <meshStandardMaterial
              color={i % 2 === 0 ? '#7b2cbf' : '#ff006e'}
              emissive={i % 2 === 0 ? '#7b2cbf' : '#ff006e'}
              emissiveIntensity={0.5}
            />
          </mesh>
        </Float>
      ))}
    </group>
  )
}

function Scene3D() {
  return (
    <div className="fixed inset-0 -z-10">
      <Canvas camera={{ position: [0, 0, 10], fov: 75 }}>
        <color attach="background" args={['#0a0e27']} />
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#7b2cbf" />
        <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
        <FloatingShield />
        <FloatingParticles />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.5} />
      </Canvas>
    </div>
  )
}

export default Scene3D
