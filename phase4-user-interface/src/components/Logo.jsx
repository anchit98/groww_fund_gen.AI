import React from 'react'

const Logo = ({ size = 32 }) => (
  <img
    src="/groww-logo.webp?v=2"
    alt="Groww logo"
    className="rounded-[8px] object-cover"
    style={{
      width: size,
      height: size,
    }}
  />
)

export default Logo
